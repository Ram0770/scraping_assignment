# Multi-Source Web Scraping & Data Consolidation Pipeline

A small ETL pipeline that scrapes **Books to Scrape** (~1,000 books / 50 pages) and **Quotes to Scrape**
(100 quotes / 10 pages), cleans and validates the records, removes duplicates, and writes one tidy CSV,
a JSON summary report and a log file. One command runs everything: `python main.py`.

```
Scrape (both sites) -> Clean -> Validate -> Deduplicate -> Consolidate -> Save files
```

## Python version
Python 3.10 - 3.12 (developed on 3.12).

## Setup
```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Dependencies
`requests`, `beautifulsoup4`, `lxml`, `pytest` (tests only). Versions are pinned in `requirements.txt`.
Everything else is the standard library (`csv`, `json`, `logging`, `re`, `urllib.parse`, `time`, `pathlib`,
`hashlib`, `datetime`, `argparse`).

## How to run
```bash
python main.py                    # full run (visits every book detail page; ~10+ minutes at 0.5s/request)
python main.py --skip-details     # fast run: ~60 requests, category/description stay empty
python main.py --max-pages 2      # quick smoke test
python main.py --delay 1.0        # slower / politer
python -m pytest                  # unit + offline end-to-end tests (no internet needed)
```
Other flags: `--output-dir`, `--log-dir`. Defaults live in `config.py`.

Outputs: `output/final_dataset.csv`, `output/summary_report.json`, `logs/scraper.log`.

## Project structure
```
scrapers/   base_scraper.py (session, retries, delay, pagination loop), books_scraper.py, quotes_scraper.py
processing/ cleaning.py, validation.py, deduplication.py   (pure functions, no internet)
tests/      test_cleaning.py, test_validation.py, test_deduplication.py, test_pipeline_offline.py
main.py     connects the stages, writes outputs      config.py   all settings
```
Rule of thumb: touches the internet -> `scrapers/`; only transforms data -> `processing/`; connects stages -> `main.py`.

## Step 1 - Observations on the sites
| Item | Books to Scrape | Quotes to Scrape |
| --- | --- | --- |
| One record | `article.product_pod` | `div.quote` |
| Main text | `h3 > a` - full title in the `title` attribute (visible text is truncated with `...`) | `span.text` (wrapped in curly quotes) |
| Price | `p.price_color` (`£51.77`) | none |
| Rating | class on `p.star-rating` (`Three`) | none |
| Availability | `p.availability` | none |
| Category / description | only on the detail page: breadcrumb (`ul.breadcrumb`) and `#product_description` + next `<p>` | none |
| Author | none | `small.author` |
| Tags | none | `div.tags a.tag` (zero or more) |
| Link | `h3 > a[href]` (relative) | `a[href^="/author/"]` (author page) |
| Next page | `li.next > a` (relative href) | `li.next > a` |

Both sites are plain server-rendered HTML, so Requests + BeautifulSoup is enough; Selenium/Playwright would only add overhead.

## Pagination
`BaseScraper.scrape()` starts at the home page, parses it, looks for `li.next > a`, converts the relative
link with `urljoin`, and repeats until no "next" link exists. Page counts are never hard-coded. A `visited`
set prevents infinite loops and `--max-pages` allows quick tests.

## Data model
One row layout for both sources; cells that do not apply are empty (never invented).

| Column | Books | Quotes |
| --- | --- | --- |
| `source` | Books to Scrape | Quotes to Scrape |
| `source_url` | book detail page URL | URL of the listing page where the quote appeared (documented choice) |
| `name_or_title` | title | quote text (quotation marks removed) |
| `category` | from detail page (empty with `--skip-details` or if the detail page fails) | empty |
| `price` | float (e.g. 51.77) | empty |
| `rating` | integer 1-5 | empty |
| `author` | empty | author name |
| `tags` | empty | `tag1;tag2` (lowercase, sorted, unique) |
| `description` | from detail page or empty | empty |
| `availability` | e.g. "In stock" (extra column) | empty |
| `author_url` | empty | author page URL (extra column) |
| `scraped_at` | UTC ISO timestamp | UTC ISO timestamp |

The schema was chosen so every row has identical columns without fake values (e.g. no quote price of 0).
`availability` and `author_url` are small additions because the assignment text lists availability and author
information as available fields.

## Cleaning approach (`processing/cleaning.py`)
Small single-purpose functions: `clean_text` (collapses spaces/tabs/newlines/NBSP, empty -> `None`),
`strip_quotes`, `clean_price` (`£51.77` -> `51.77`, also tolerates `Â£` and thousands separators),
`clean_rating` (`Three` -> 3), `clean_tags`, `normalize_url` (absolute, http/https only), plus
`clean_book` / `clean_quote` mapping raw dicts to the common model. Responses are decoded as UTF-8 so `£` is correct.

## Validation approach (`processing/validation.py`)
`validate_record` returns a list of problem codes (empty = valid), so the summary can show *why* records were rejected:
`unknown_source`, `missing_name`, `invalid_url`, `invalid_price`, `invalid_rating`, plus source-specific
`missing_price` (books) and `missing_author` (quotes). Rejected records are logged as WARNING and counted;
the run continues. One record may have several reasons, so reason counts can exceed the rejected-record count.

## Deduplication approach (`processing/deduplication.py`)
A fingerprint = SHA-256 of the normalized identifying fields (lowercase, punctuation removed, whitespace collapsed):
- **Books:** source + title
- **Quotes:** source + author + first 50 characters of the (normalized) quote text

So `"Example Book Title"`, `" Example Book Title "` and `"EXAMPLE BOOK TITLE"` are one record. Duplicates are
**removed** (first occurrence kept) rather than flagged, because the final file should be a clean, analysis-ready
table; every removal is logged and counted in the summary. The practice sites have no duplicates, so the logic is
proven by unit tests with deliberately duplicated records.

## Error-handling approach
- Shared `requests.Session` with User-Agent, 10 s timeout and retries with exponential backoff (1s, 2s, 4s) on HTTP 429/500/502/503/504 and connection errors.
- A failed listing page is logged as ERROR and stops *that source only*; the other source still runs.
- A failed book detail page only leaves category/description empty for that book.
- Each record is parsed in `try/except`; missing elements are handled with `select_one()` + `None` checks.
- Each source runs inside its own `try/except` in `main.py`; cleaning errors are caught per record.
- 0.5 s pause between all requests (configurable).

## Output description
- `output/final_dataset.csv` - one row per unique valid record, fixed column order, UTF-8.
- `output/summary_report.json` - per source: raw collected, cleaned, rejected (with reasons), duplicates, final, pages scraped, failed pages, status; totals; run start/end/duration; `csv_row_count`; and a `reconciles` check (`raw - cleaning_errors - rejected - duplicates == final`).
- `logs/scraper.log` - timestamped INFO per page, WARNING per rejected record/duplicate, ERROR per failed request.

## Assumptions
- The site layouts match the selectors in the observations table.
- Quote identity = author + first 50 normalized characters of text.
- A book without a price is invalid; a quote without an author is invalid.

## Known limitations
- Full run with detail pages is slow because of the polite 0.5 s delay (~1,000 extra requests); sequential, no async.
- No checkpoint/resume or incremental scraping.
- Selectors are tied to the current HTML of the practice sites.
- Quote `source_url` is the listing page, so several quotes share a URL.
- If a source's listing page fails after retries, remaining pages of that source are not scraped.

## Production improvements I would make
Checkpoint/resume, incremental runs keyed by fingerprint, async fetching with a rate limiter, a database
(PostgreSQL/MongoDB) instead of CSV, scheduled runs with alerting on schema/selector changes, and Docker packaging.

## AI usage summary
See `AI_USAGE.md`.
