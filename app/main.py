from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Profile
from app.parser import AGE_GROUPS, parse_natural_language
from app.schemas import ProfileOut

VALID_SORT_COLUMNS = {
    "age": Profile.age,
    "created_at": Profile.created_at,
    "gender_probability": Profile.gender_probability,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Intelligence Query Engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, __: RequestValidationError):
    return error_response(422, "Invalid query parameters")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Server failure"
    return error_response(exc.status_code, message)


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, __: Exception):
    return error_response(500, "Server failure")


def _apply_filters(stmt, filters: dict):
    if filters.get("gender"):
        stmt = stmt.where(Profile.gender == filters["gender"])
    if filters.get("age_group"):
        stmt = stmt.where(Profile.age_group == filters["age_group"])
    if filters.get("country_id"):
        stmt = stmt.where(Profile.country_id == filters["country_id"])
    if filters.get("min_age") is not None:
        stmt = stmt.where(Profile.age >= filters["min_age"])
    if filters.get("max_age") is not None:
        stmt = stmt.where(Profile.age <= filters["max_age"])
    if filters.get("min_gender_probability") is not None:
        stmt = stmt.where(Profile.gender_probability >= filters["min_gender_probability"])
    if filters.get("min_country_probability") is not None:
        stmt = stmt.where(Profile.country_probability >= filters["min_country_probability"])
    return stmt


def _query_profiles(db: Session, filters: dict, page: int, limit: int, sort_by: str, order: str):
    base_stmt = _apply_filters(select(Profile), filters)
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.scalar(total_stmt) or 0

    sort_column = VALID_SORT_COLUMNS[sort_by]
    if order == "desc":
        sort_column = sort_column.desc()

    data_stmt = base_stmt.order_by(sort_column).offset((page - 1) * limit).limit(limit)
    rows = db.scalars(data_stmt).all()
    return total, rows


def _validate_filter_values(
    gender: str | None,
    age_group: str | None,
    country_id: str | None,
    min_age: int | None,
    max_age: int | None,
):
    if gender is not None and gender not in {"male", "female"}:
        raise HTTPException(status_code=422, detail="Invalid query parameters")
    if age_group is not None and age_group not in AGE_GROUPS:
        raise HTTPException(status_code=422, detail="Invalid query parameters")
    if country_id is not None and (len(country_id) != 2 or not country_id.isalpha()):
        raise HTTPException(status_code=422, detail="Invalid query parameters")
    if min_age is not None and max_age is not None and min_age > max_age:
        raise HTTPException(status_code=422, detail="Invalid query parameters")


@app.get("/")
def healthcheck():
    return {"status": "success", "message": "Intelligence Query Engine is running"}


@app.get("/api/profiles")
def get_profiles(
    db: Annotated[Session, Depends(get_db)],
    gender: str | None = Query(default=None),
    age_group: str | None = Query(default=None),
    country_id: str | None = Query(default=None),
    min_age: int | None = Query(default=None, ge=0),
    max_age: int | None = Query(default=None, ge=0),
    min_gender_probability: float | None = Query(default=None, ge=0.0, le=1.0),
    min_country_probability: float | None = Query(default=None, ge=0.0, le=1.0),
    sort_by: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    if sort_by not in VALID_SORT_COLUMNS or order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="Invalid query parameters")

    norm_country_id = country_id.upper() if country_id else None
    _validate_filter_values(gender, age_group, norm_country_id, min_age, max_age)

    filters = {
        "gender": gender,
        "age_group": age_group,
        "country_id": norm_country_id,
        "min_age": min_age,
        "max_age": max_age,
        "min_gender_probability": min_gender_probability,
        "min_country_probability": min_country_probability,
    }

    total, rows = _query_profiles(db, filters, page, limit, sort_by, order)
    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [ProfileOut.model_validate(item).model_dump() for item in rows],
    }


@app.get("/api/profiles/search")
def search_profiles(
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    if q is None or not q.strip():
        raise HTTPException(status_code=400, detail="Missing or empty parameter")

    parsed = parse_natural_language(q)
    if not parsed:
        return error_response(400, "Unable to interpret query")

    total, rows = _query_profiles(
        db=db,
        filters=parsed,
        page=page,
        limit=limit,
        sort_by="created_at",
        order="desc",
    )
    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [ProfileOut.model_validate(item).model_dump() for item in rows],
    }
