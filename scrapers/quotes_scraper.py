"""Quotes to Scrape: selectors and parsing for this site only."""
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper, utc_now_iso

logger = logging.getLogger(__name__)


class QuotesScraper(BaseScraper):
    source_name = config.SOURCE_QUOTES

    def __init__(self, start_url: str = config.QUOTES_START_URL, **kwargs):
        super().__init__(start_url, **kwargs)

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        records = []
        for div in soup.select("div.quote"):
            try:
                text = div.select_one("span.text")
                author = div.select_one("small.author")
                author_link = div.select_one('a[href^="/author/"]')
                records.append({
                    "source": self.source_name,
                    "text": text.get_text() if text else None,
                    "author": author.get_text() if author else None,
                    "tags_raw": [t.get_text() for t in div.select("div.tags a.tag")],
                    "source_url": page_url,    # documented choice: page where the quote appeared
                    "author_url": urljoin(page_url, author_link["href"]) if author_link and author_link.get("href") else None,
                    "scraped_at": utc_now_iso(),
                })
            except Exception as exc:
                self.record_errors += 1
                logger.warning("[%s] Skipping unparsable record on %s: %s", self.source_name, page_url, exc)
        return records
