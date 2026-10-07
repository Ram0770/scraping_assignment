"""Duplicate detection via normalized fingerprints.

Books  : source + title
Quotes : source + author + first 50 characters of the quote text
Normalization: lowercase, drop punctuation, collapse whitespace, SHA-256.
Duplicates are REMOVED from the final dataset (first occurrence wins) and logged.
"""
import hashlib
import logging
import re

import config

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", "", (text or "").lower())
    return " ".join(text.split())


def make_fingerprint(rec: dict) -> str:
    source = rec.get("source") or ""
    title = rec.get("name_or_title") or ""
    if source == config.SOURCE_QUOTES:
        key = f"{source} {rec.get('author') or ''} {_normalize(title)[:50]}"
    else:
        key = f"{source} {title}"
    return hashlib.sha256(_normalize(key).encode("utf-8")).hexdigest()


def find_duplicates(records: list[dict]) -> tuple[list[dict], list[dict]]:
    seen, unique, dupes = set(), [], []
    for rec in records:
        fp = make_fingerprint(rec)
        if fp in seen:
            dupes.append(rec)
            logger.warning("Duplicate removed: [%s] %.60s", rec.get("source"), rec.get("name_or_title"))
        else:
            seen.add(fp)
            unique.append(rec)
    return unique, dupes
