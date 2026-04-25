import re
from typing import Any

import pycountry

AGE_GROUPS = {"child", "teenager", "adult", "senior"}
AGE_GROUP_TERMS = {
    "child": "child",
    "children": "child",
    "teenager": "teenager",
    "teenagers": "teenager",
    "adult": "adult",
    "adults": "adult",
    "senior": "senior",
    "seniors": "senior",
}
GENDER_WORDS = {
    "male": "male",
    "males": "male",
    "man": "male",
    "men": "male",
    "female": "female",
    "females": "female",
    "woman": "female",
    "women": "female",
}


def _build_country_lookup() -> dict[str, str]:
    country_lookup: dict[str, str] = {}
    for country in pycountry.countries:
        country_lookup[country.name.lower()] = country.alpha_2
        official_name = getattr(country, "official_name", None)
        if official_name:
            country_lookup[official_name.lower()] = country.alpha_2
        common_name = getattr(country, "common_name", None)
        if common_name:
            country_lookup[common_name.lower()] = country.alpha_2
    return country_lookup


COUNTRY_LOOKUP = _build_country_lookup()
COUNTRY_CODES = {country.alpha_2 for country in pycountry.countries}


def _extract_country_id(query: str) -> str | None:
    upper_code_match = re.search(r"\b([A-Z]{2})\b", query)
    if upper_code_match:
        code = upper_code_match.group(1)
        if code in COUNTRY_CODES:
            return code

    lowered = query.lower()
    for country_name in sorted(COUNTRY_LOOKUP.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(country_name)}\b", lowered):
            return COUNTRY_LOOKUP[country_name]

    from_match = re.search(r"\b(?:from|in)\s+([a-z\s]+)", lowered)
    if from_match:
        chunk = from_match.group(1).strip()
        chunk = re.split(r"\b(?:and|with|above|below|under|over)\b", chunk)[0].strip()
        if chunk in COUNTRY_LOOKUP:
            return COUNTRY_LOOKUP[chunk]

    return None


def parse_natural_language(query: str) -> dict[str, Any] | None:
    parsed: dict[str, Any] = {}
    q = query.strip()
    if not q:
        return None

    lower_q = q.lower()

    gender_hits = {normalized for word, normalized in GENDER_WORDS.items() if re.search(rf"\b{word}\b", lower_q)}
    if len(gender_hits) == 1:
        parsed["gender"] = gender_hits.pop()

    for term, normalized_group in AGE_GROUP_TERMS.items():
        if re.search(rf"\b{term}\b", lower_q):
            parsed["age_group"] = normalized_group
            break

    if re.search(r"\byoung\b", lower_q):
        parsed["min_age"] = 16
        parsed["max_age"] = 24

    above_match = re.search(r"\b(?:above|over|older than|at least)\s+(\d{1,3})\b", lower_q)
    if above_match:
        min_age = int(above_match.group(1))
        parsed["min_age"] = max(min_age, parsed.get("min_age", min_age))

    below_match = re.search(r"\b(?:below|under|younger than|at most)\s+(\d{1,3})\b", lower_q)
    if below_match:
        max_age = int(below_match.group(1))
        parsed["max_age"] = min(max_age, parsed.get("max_age", max_age))

    between_match = re.search(r"\b(?:between)\s+(\d{1,3})\s+(?:and|to)\s+(\d{1,3})\b", lower_q)
    if between_match:
        a = int(between_match.group(1))
        b = int(between_match.group(2))
        parsed["min_age"] = min(a, b)
        parsed["max_age"] = max(a, b)

    country_id = _extract_country_id(q)
    if country_id:
        parsed["country_id"] = country_id

    if "min_age" in parsed and "max_age" in parsed and parsed["min_age"] > parsed["max_age"]:
        return None

    return parsed or None
