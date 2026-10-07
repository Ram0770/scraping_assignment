"""Shared networking + pagination logic. Anything that touches the internet lives in scrapers/."""
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

import config

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_session(max_retries: int = config.MAX_RETRIES,
                   backoff: float = config.BACKOFF_FACTOR) -> requests.Session:
    """One session with User-Agent and automatic retries (exponential backoff) for temporary errors."""
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    retries = Retry(total=max_retries, backoff_factor=backoff,
                    status_forcelist=config.RETRY_STATUSES,
                    allowed_methods=["GET", "HEAD"])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class BaseScraper(ABC):
    source_name: str = ""

    def __init__(self, start_url: str, session: requests.Session | None = None,
                 delay: float = config.REQUEST_DELAY, timeout: int = config.REQUEST_TIMEOUT,
                 max_pages: int | None = None):
        self.start_url = start_url
        self.session = session or create_session()
        self.delay = delay
        self.timeout = timeout
        self.max_pages = max_pages
        self.pages_scraped = 0
        self.failed_pages: list[str] = []
        self.record_errors = 0

    # ---- networking -------------------------------------------------
    def fetch(self, url: str) -> BeautifulSoup | None:
        """Download and parse one page. Returns None (and logs ERROR) on any request failure."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = "utf-8"          # keeps the pound sign correct
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as exc:
            logger.error("[%s] Failed to fetch %s: %s", self.source_name, url, exc)
            self.failed_pages.append(url)
            return None
        finally:
            time.sleep(self.delay)               # be polite to the server

    # ---- pagination -------------------------------------------------
    @abstractmethod
    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        """Return raw dictionaries for every record found on one page."""

    @staticmethod
    def find_next_url(soup: BeautifulSoup, page_url: str) -> str | None:
        link = soup.select_one("li.next > a")
        if link and link.get("href"):
            return urljoin(page_url, link["href"])
        return None

    def scrape(self) -> list[dict]:
        """Follow the 'next' link until there is none. Never needs to know the page count."""
        url, page, records, visited = self.start_url, 1, [], set()
        while url and url not in visited:
            if self.max_pages and page > self.max_pages:
                logger.info("[%s] Reached --max-pages limit (%d)", self.source_name, self.max_pages)
                break
            visited.add(url)
            logger.info("[%s] Page %d: %s", self.source_name, page, url)
            soup = self.fetch(url)
            if soup is None:
                logger.error("[%s] Stopping this source after page failure.", self.source_name)
                break
            records.extend(self.parse_page(soup, url))
            self.pages_scraped += 1
            url = self.find_next_url(soup, url)
            page += 1
        logger.info("[%s] Done: %d raw records from %d pages", self.source_name, len(records), self.pages_scraped)
        return records
