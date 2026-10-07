"""Pure cleaning functions: a value in, a cleaned value out. No internet, no files."""
import re
from urllib.parse import urljoin

import config

RATING_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_QUOTE_CHARS = "\u201c\u201d\u2018\u2019\"'"


def clean_text(value):
    """Collapse tabs/newlines/NBSP/repeated spaces; empty becomes None."""
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return text or None


def strip_quotes(value):
    """Remove the curly (or straight) quotation marks wrapped around a quote."""
    text = clean_text(value)
    if text is None:
        return None
    return text.strip(_QUOTE_CHARS + " ") or None


def clean_price(raw):
    """'£51.77' (or mojibake 'Â£51.77', or '1,234.50') -> float; unparsable -> None."""
    if raw is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(raw).replace(",", ""))
    return float(match.group()) if match else None


def clean_rating(raw):
    """'star-rating Three' / 'Three' / '3' -> 3; unknown -> None."""
    if raw is None:
        return None
    for word in str(raw).lower().split():
        if word in RATING_MAP:
            return RATING_MAP[word]
        if word.isdigit():
            return int(word)
    return None


def clean_tags(tags):
    """List (or ';' string) of tags -> lowercase, de-duplicated, sorted, joined with ';'."""
    if tags is None:
        return None
    if isinstance(tags, str):
        tags = tags.split(";")
    cleaned = sorted({clean_text(x).lower() for x in tags if clean_text(x)})
    return ";".join(cleaned) or None


def normalize_url(url, base=None):
    """Make a URL absolute and require http(s). Returns None if it cannot be made valid."""
    url = clean_text(url)
    if url is None:
        return None
    if base:
        url = urljoin(base, url)
    return url if url.lower().startswith(("http://", "https://")) else None


def clean_book(raw: dict) -> dict:
    """Raw Books-to-Scrape dict -> common data model."""
    return {
        "source": clean_text(raw.get("source")),
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": clean_text(raw.get("title")),
        "category": clean_text(raw.get("category_raw")),
        "price": clean_price(raw.get("price_raw")),
        "rating": clean_rating(raw.get("rating_raw")),
        "author": None,
        "tags": None,
        "description": clean_text(raw.get("description_raw")),
        "availability": clean_text(raw.get("availability_raw")),
        "author_url": None,
        "scraped_at": raw.get("scraped_at"),
    }


def clean_quote(raw: dict) -> dict:
    """Raw Quotes-to-Scrape dict -> common data model."""
    return {
        "source": clean_text(raw.get("source")),
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": strip_quotes(raw.get("text")),
        "category": None,
        "price": None,
        "rating": None,
        "author": clean_text(raw.get("author")),
        "tags": clean_tags(raw.get("tags_raw")),
        "description": None,
        "availability": None,
        "author_url": normalize_url(raw.get("author_url")),
        "scraped_at": raw.get("scraped_at"),
    }


CLEANERS = {config.SOURCE_BOOKS: clean_book, config.SOURCE_QUOTES: clean_quote}
