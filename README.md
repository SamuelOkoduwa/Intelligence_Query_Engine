# Intelligence Query Engine

A FastAPI + SQLAlchemy backend for demographic profile retrieval with:
- Advanced filtering (combinable)
- Sorting
- Pagination
- Rule-based natural language query parsing

## 1) Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- SQLite by default (switchable via `DATABASE_URL`)

## 2) Database Schema

Table: `profiles`

- `id` (UUID v7, primary key)
- `name` (VARCHAR, unique)
- `gender` (VARCHAR: male/female)
- `gender_probability` (FLOAT)
- `age` (INT)
- `age_group` (VARCHAR: child/teenager/adult/senior)
- `country_id` (VARCHAR(2), ISO code)
- `country_name` (VARCHAR)
- `country_probability` (FLOAT)
- `created_at` (TIMESTAMP, UTC)

Indexes are added on filter/sort columns to reduce scan-heavy reads.

## 3) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional DB config:

```bash
export DATABASE_URL="sqlite:///./profiles.db"
```

## 4) Seed Data

Place the provided 2026 JSON file at:

```text
data/profiles_2026.json
```

Then run:

```bash
python -m scripts.seed_profiles --file data/profiles_2026.json
```

Seed behavior is idempotent by unique `name`:
- Existing names are updated
- New names are inserted
- Re-running does not create duplicates

## 5) Run Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Base URL: `http://localhost:8000`

## 6) Endpoints

### GET `/api/profiles`

Supports filtering + sorting + pagination together.

Filters:
- `gender`
- `age_group`
- `country_id`
- `min_age`
- `max_age`
- `min_gender_probability`
- `min_country_probability`

Sorting:
- `sort_by`: `age | created_at | gender_probability`
- `order`: `asc | desc`

Pagination:
- `page` default `1`
- `limit` default `10`, max `50`

Example:

```bash
curl "http://localhost:8000/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10"
```

### GET `/api/profiles/search`

Natural language parsing endpoint.

Params:
- `q` (required)
- `page` default `1`
- `limit` default `10`, max `50`

Example:

```bash
curl "http://localhost:8000/api/profiles/search?q=young%20males%20from%20nigeria"
```

## 7) Natural Language Parsing Approach (Rule-Based)

No AI/LLM is used. Parsing is deterministic with regex and keyword matching.

### Supported Keyword Mappings

Gender words:
- `male`, `males`, `man`, `men` -> `gender=male`
- `female`, `females`, `woman`, `women` -> `gender=female`
- If both male and female terms appear, gender filter is omitted.

Age group words:
- `child` -> `age_group=child`
- `teenager` or `teenagers` -> `age_group=teenager`
- `adult` or `adults` -> `age_group=adult`
- `senior` or `seniors` -> `age_group=senior`

Special age keyword:
- `young` -> `min_age=16` and `max_age=24` (parsing rule only, not stored as age group)

Numeric age constraints:
- `above 30`, `over 30`, `older than 30`, `at least 30` -> `min_age=30`
- `below 40`, `under 40`, `younger than 40`, `at most 40` -> `max_age=40`
- `between 18 and 25` / `between 18 to 25` -> `min_age=18`, `max_age=25`

Country parsing:
- Matches full country names via `pycountry` (e.g., `nigeria` -> `country_id=NG`)
- Also supports explicit 2-letter uppercase ISO code in query (e.g., `from NG`)

### Parsing Logic

1. Normalize input text.
2. Extract gender intent.
3. Extract age-group keywords.
4. Extract age bounds (`young`, above/below/between).
5. Extract country intent.
6. Merge results into a filter object.
7. Reject contradictions (e.g., `min_age > max_age`).
8. If no interpretable filters are found, return:
   - `{ "status": "error", "message": "Unable to interpret query" }`

## 8) Error Format

All errors use:

```json
{ "status": "error", "message": "<error message>" }
```

Used statuses:
- `400` Missing or empty parameter / unable to interpret query
- `422` Invalid query parameters
- `404` Profile not found (reserved pattern)
- `500` Server failure

## 9) CORS and Time Format

- CORS is enabled with `Access-Control-Allow-Origin: *`
- Timestamps are returned as UTC ISO 8601 strings (`...Z`)

## 10) Performance Notes

- Query filters are translated directly into SQL predicates.
- Filter and sort columns are indexed.
- Pagination uses `OFFSET/LIMIT` with filtered counts.

## 11) Limitations

- Parser does not resolve misspellings (e.g., `nigerai`).
- Parser handles a fixed set of age phrases and does not interpret complex language like "not older than about thirty".
- Parser does not infer synonyms beyond supported keywords.
- Gender parsing is binary (`male`/`female`) per assessment schema.
- If the dataset has duplicate names, idempotent seeding uses `name` uniqueness and will treat that as one logical profile.
