"""Books to Scrape: selectors and parsing for this site only."""
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper, utc_now_iso

logger = logging.getLogger(__name__)


class BooksScraper(BaseScraper):
    source_name = config.SOURCE_BOOKS

    def __init__(self, start_url: str = config.BOOKS_START_URL, fetch_details: bool = True, **kwargs):
        super().__init__(start_url, **kwargs)
        self.fetch_details = fetch_details

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        records = []
        for article in soup.select("article.product_pod"):
            try:
                record = self.parse_listing(article, page_url)
                if self.fetch_details and record.get("source_url"):
                    record.update(self.parse_detail(record["source_url"]))
                records.append(record)
            except Exception as exc:               # one bad record must not stop the page
                self.record_errors += 1
                logger.warning("[%s] Skipping unparsable record on %s: %s", self.source_name, page_url, exc)
        return records

    def parse_listing(self, article, page_url: str) -> dict:
        link = article.select_one("h3 > a")
        price = article.select_one("p.price_color")
        rating = article.select_one("p.star-rating")
        avail = article.select_one("p.availability")
        return {
            "source": self.source_name,
            # full title is in the title attribute (visible text is cut off with "...")
            "title": (link.get("title") or link.get_text()) if link else None,
            "source_url": urljoin(page_url, link["href"]) if link and link.get("href") else None,
            "price_raw": price.get_text() if price else None,
            "rating_raw": " ".join(rating.get("class", [])) if rating else None,
            "availability_raw": avail.get_text() if avail else None,
            "category_raw": None,
            "description_raw": None,
            "scraped_at": utc_now_iso(),
        }

    def parse_detail(self, url: str) -> dict:
        """Category and description live only on the detail page. Failure is non-fatal."""
        soup = self.fetch(url)
        if soup is None:
            logger.warning("[%s] Detail page unavailable, category/description left empty: %s", self.source_name, url)
            return {}
        crumbs = soup.select("ul.breadcrumb li a")
        category = crumbs[-1].get_text() if len(crumbs) >= 3 else None   # Home > Books > <Category>
        desc_header = soup.select_one("#product_description")
        desc = desc_header.find_next_sibling("p") if desc_header else None
        return {
            "category_raw": category,
            "description_raw": desc.get_text() if desc else None,
        }
