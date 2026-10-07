"""Entry point: python main.py   ->  scrape -> clean -> validate -> deduplicate -> consolidate -> save."""
import argparse
import csv
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import config
from processing.cleaning import CLEANERS
from processing.deduplication import find_duplicates
from processing.validation import validate_record
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper

logger = logging.getLogger("pipeline")


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    file_handler = logging.FileHandler(log_dir / "scraper.log", mode="w", encoding="utf-8")
    console = logging.StreamHandler()
    for h in (file_handler, console):
        h.setFormatter(fmt)
        root.addHandler(h)


def clean_and_validate(source: str, raw_records: list[dict]) -> tuple[list[dict], dict]:
    """Clean then validate one source's raw records. Never raises for a bad record."""
    cleaner = CLEANERS[source]
    valid, rejected = [], Counter()
    cleaning_errors = 0
    cleaned_count = 0
    for raw in raw_records:
        try:
            rec = cleaner(raw)
        except Exception as exc:
            cleaning_errors += 1
            logger.warning("Cleaning failed for a %s record: %s", source, exc)
            continue
        cleaned_count += 1
        problems = validate_record(rec)
        if problems:
            for p in problems:
                rejected[p] += 1
            logger.warning("Rejected [%s] %.60s -> %s", source, rec.get("name_or_title"), problems)
        else:
            valid.append(rec)
    stats = {
        "raw_collected": len(raw_records),
        "cleaning_errors": cleaning_errors,
        "cleaned": cleaned_count,
        "rejected_records": cleaned_count - len(valid),
        "rejected_by_reason": dict(rejected),   # one record can have several reasons
        "valid": len(valid),
    }
    return valid, stats


def run_source(scraper) -> tuple[list[dict], dict]:
    """Scrape one source; any unexpected crash is logged and does not stop the other source."""
    name = scraper.source_name
    try:
        raw = scraper.scrape()
        if not scraper.failed_pages:
            status = "ok"
        else:
            status = "failed" if scraper.pages_scraped == 0 else "partial"
        error = None
    except Exception as exc:
        logger.exception("[%s] Source failed unexpectedly: %s", name, exc)
        raw, status, error = [], "failed", str(exc)
    valid, stats = clean_and_validate(name, raw)
    stats.update({
        "status": status,
        "error": error,
        "pages_scraped": scraper.pages_scraped,
        "failed_pages": scraper.failed_pages,
        "record_parse_errors": scraper.record_errors,
    })
    return valid, stats


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def write_summary(stats: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)


def run_pipeline(args) -> dict:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    out_dir = Path(args.output_dir)
    common = {"delay": args.delay, "max_pages": args.max_pages}
    scrapers = [
        BooksScraper(fetch_details=not args.skip_details, **common),
        QuotesScraper(**common),
    ]

    all_valid, per_source = [], {}
    for scraper in scrapers:
        valid, stats = run_source(scraper)
        all_valid.extend(valid)
        per_source[scraper.source_name] = stats

    unique, dupes = find_duplicates(all_valid)
    dupe_counts = Counter(d["source"] for d in dupes)
    for name, stats in per_source.items():
        stats["duplicates_removed"] = dupe_counts.get(name, 0)
        stats["final"] = stats["valid"] - stats["duplicates_removed"]
        # raw - cleaning_errors - rejected - duplicates == final
        stats["reconciles"] = (stats["raw_collected"] - stats["cleaning_errors"]
                               - stats["rejected_records"] - stats["duplicates_removed"] == stats["final"])

    write_csv(unique, out_dir / "final_dataset.csv")

    duration = round(time.perf_counter() - t0, 2)
    summary = {
        "run": {
            "start_time": started.isoformat(timespec="seconds"),
            "end_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "fetch_book_details": not args.skip_details,
            "request_delay_seconds": args.delay,
            "max_pages": args.max_pages,
        },
        "sources": per_source,
        "totals": {
            "raw_collected": sum(s["raw_collected"] for s in per_source.values()),
            "cleaned": sum(s["cleaned"] for s in per_source.values()),
            "rejected_records": sum(s["rejected_records"] for s in per_source.values()),
            "duplicates_removed": len(dupes),
            "final_record_count": len(unique),
        },
        "csv_row_count": len(unique),
        "all_sources_reconcile": all(s["reconciles"] for s in per_source.values()),
    }
    write_summary(summary, out_dir / "summary_report.json")
    logger.info("Finished in %.1fs: %d final records (%d duplicates, %d rejected).",
                duration, len(unique), len(dupes), summary["totals"]["rejected_records"])
    return summary


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Multi-source web scraping and data consolidation pipeline.")
    p.add_argument("--output-dir", default=str(config.OUTPUT_DIR), help="where CSV/JSON are written")
    p.add_argument("--log-dir", default=str(config.LOG_DIR), help="where scraper.log is written")
    p.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="seconds between requests")
    p.add_argument("--max-pages", type=int, default=None, help="limit pages per source (for quick tests)")
    p.add_argument("--skip-details", action="store_true",
                   help="do not visit each book detail page (category/description stay empty; much faster)")
    return p.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args()
    setup_logging(Path(arguments.log_dir))
    run_pipeline(arguments)
