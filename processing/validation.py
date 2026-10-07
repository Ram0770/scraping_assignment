"""Validation: returns the list of problems for one cleaned record (empty list = valid)."""
import config


def validate_record(rec: dict) -> list[str]:
    problems = []
    source = rec.get("source")
    if source not in config.VALID_SOURCES:
        problems.append("unknown_source")
    if not rec.get("name_or_title"):
        problems.append("missing_name")
    if not str(rec.get("source_url") or "").startswith(("http://", "https://")):
        problems.append("invalid_url")

    price = rec.get("price")
    if price is not None and (isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0):
        problems.append("invalid_price")
    rating = rec.get("rating")
    if rating is not None and (isinstance(rating, bool) or rating not in (1, 2, 3, 4, 5)):
        problems.append("invalid_rating")

    # source-specific required fields
    if source == config.SOURCE_BOOKS and price is None:
        problems.append("missing_price")
    if source == config.SOURCE_QUOTES and not rec.get("author"):
        problems.append("missing_author")
    return problems
