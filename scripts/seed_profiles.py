import argparse
import json
from pathlib import Path

from sqlalchemy import select
from uuid6 import uuid7

from app.database import Base, SessionLocal, engine
from app.models import Profile


def derive_age_group(age: int) -> str:
    if age <= 12:
        return "child"
    if age <= 19:
        return "teenager"
    if age <= 64:
        return "adult"
    return "senior"


def normalize_profile(raw: dict) -> dict:
    age = int(raw["age"])
    return {
        "name": str(raw["name"]).strip(),
        "gender": str(raw["gender"]).strip().lower(),
        "gender_probability": float(raw["gender_probability"]),
        "age": age,
        "age_group": str(raw.get("age_group") or derive_age_group(age)).strip().lower(),
        "country_id": str(raw["country_id"]).strip().upper(),
        "country_name": str(raw["country_name"]).strip(),
        "country_probability": float(raw["country_probability"]),
    }


def seed(data_file: Path) -> tuple[int, int]:
    Base.metadata.create_all(bind=engine)

    payload = json.loads(data_file.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        # unwrap common wrapper keys e.g. {"profiles": [...]} or {"data": [...]}
        for key in ("profiles", "data", "results", "records"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("Seed file must contain a JSON array")

    normalized_rows = [normalize_profile(item) for item in payload]
    names = [row["name"] for row in normalized_rows]

    created = 0
    updated = 0

    with SessionLocal() as db:
        existing_rows = db.scalars(select(Profile).where(Profile.name.in_(names))).all()
        existing_by_name = {row.name: row for row in existing_rows}

        for row in normalized_rows:
            existing = existing_by_name.get(row["name"])
            if existing:
                existing.gender = row["gender"]
                existing.gender_probability = row["gender_probability"]
                existing.age = row["age"]
                existing.age_group = row["age_group"]
                existing.country_id = row["country_id"]
                existing.country_name = row["country_name"]
                existing.country_probability = row["country_probability"]
                updated += 1
            else:
                db.add(Profile(id=str(uuid7()), **row))
                created += 1

        db.commit()

    return created, updated


def main():
    parser = argparse.ArgumentParser(description="Seed profiles table from a JSON file")
    parser.add_argument(
        "--file",
        default="data/profiles_2026.json",
        help="Path to JSON file with 2026 profile records",
    )
    args = parser.parse_args()

    data_path = Path(args.file)
    if not data_path.exists():
        raise FileNotFoundError(f"Seed file not found: {data_path}")

    created, updated = seed(data_path)
    print(f"Seeding complete. created={created} updated={updated}")


if __name__ == "__main__":
    main()
