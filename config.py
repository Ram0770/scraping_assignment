"""Central settings so nothing is hard-coded inside the scrapers."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

BOOKS_START_URL = "https://books.toscrape.com/"
QUOTES_START_URL = "https://quotes.toscrape.com/"

SOURCE_BOOKS = "Books to Scrape"
SOURCE_QUOTES = "Quotes to Scrape"
VALID_SOURCES = {SOURCE_BOOKS, SOURCE_QUOTES}

USER_AGENT = "ScrapingAssignment/1.0 (learning project)"
REQUEST_TIMEOUT = 10        # seconds per request
REQUEST_DELAY = 0.5         # polite pause between requests (seconds)
MAX_RETRIES = 3             # urllib3 retries; backoff 1s, 2s, 4s
BACKOFF_FACTOR = 1.0
RETRY_STATUSES = [429, 500, 502, 503, 504]

OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

# Fixed CSV column order (the common data model).
COLUMNS = [
    "source", "source_url", "name_or_title", "category", "price", "rating",
    "author", "tags", "description", "availability", "author_url", "scraped_at",
]
