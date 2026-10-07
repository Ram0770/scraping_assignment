"""End-to-end test against a tiny local fake of both sites (no internet needed).
Includes a failing page (404) and a record with a missing element to prove the pipeline survives."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import main

NAV = '<li class="next"><a href="{}">next</a></li>'


def book_html(title, price, rating, href, missing_price=False):
    price_tag = "" if missing_price else f'<p class="price_color">\u00a3{price}</p>'
    return (f'<article class="product_pod"><p class="star-rating {rating}"></p>'
            f'<h3><a href="{href}" title="{title}">{title[:10]}...</a></h3>{price_tag}'
            f'<p class="instock availability"> In stock </p></article>')


def page(body, nxt=None):
    nav = f'<ul class="pager">{NAV.format(nxt)}</ul>' if nxt else ""
    return f"<html><body>{body}{nav}</body></html>"


def quote_html(text, author, tags):
    t = "".join(f'<a class="tag" href="/tag/{x}/">{x}</a>' for x in tags)
    return (f'<div class="quote"><span class="text">\u201c{text}\u201d</span>'
            f'<span>by <small class="author">{author}</small><a href="/author/{author}">(about)</a></span>'
            f'<div class="tags">{t}</div></div>')


PAGES = {
    "/books/index.html": page(book_html("Book One Title", "10.00", "Three", "b1.html")
                              + book_html("Book Two Title", "20.50", "Five", "b2.html"), "page-2.html"),
    "/books/page-2.html": page(book_html("BOOK ONE TITLE", "10.00", "Three", "b3.html")      # duplicate
                               + book_html("No Price Book", "0", "One", "b4.html", missing_price=True)),  # rejected
    "/books/b1.html": '<ul class="breadcrumb"><li><a>Home</a></li><li><a>Books</a></li><li><a>Poetry</a></li></ul>'
                      '<div id="product_description"></div><p>A nice book.</p>',
    # b2 / b3 / b4 detail pages deliberately missing -> 404, must not crash
    "/quotes/": page(quote_html("Hello world.", "Ann", ["Life", "Love"]) + quote_html("Second quote", "Bob", []), "/quotes/page/2/"),
    "/quotes/page/2/": page(quote_html("  hello   WORLD. ", "Ann", ["life"])),                    # duplicate
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        if body is None:
            self.send_response(404); self.end_headers(); return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_full_pipeline(server, tmp_path, monkeypatch):
    from scrapers.books_scraper import BooksScraper
    from scrapers.quotes_scraper import QuotesScraper
    from scrapers.base_scraper import create_session

    session = create_session(max_retries=0)
    monkeypatch.setattr(main, "BooksScraper", lambda **kw: BooksScraper(
        start_url=server + "/books/index.html", session=session, **kw))
    monkeypatch.setattr(main, "QuotesScraper", lambda **kw: QuotesScraper(
        start_url=server + "/quotes/", session=session, **kw))

    args = main.parse_args(["--output-dir", str(tmp_path), "--delay", "0"])
    summary = main.run_pipeline(args)

    rows = list(csv.DictReader(open(tmp_path / "final_dataset.csv", encoding="utf-8")))
    books = summary["sources"]["Books to Scrape"]
    quotes = summary["sources"]["Quotes to Scrape"]

    assert books["raw_collected"] == 4 and books["pages_scraped"] == 2      # followed "next" link
    assert books["rejected_by_reason"] == {"missing_price": 1}
    assert books["duplicates_removed"] == 1 and books["final"] == 2
    assert len(books["failed_pages"]) == 3                                  # 404 detail pages survived
    assert quotes["raw_collected"] == 3 and quotes["duplicates_removed"] == 1 and quotes["final"] == 2
    assert quotes["pages_scraped"] == 2
    assert summary["all_sources_reconcile"] and summary["csv_row_count"] == len(rows) == 4
    assert {r["source"] for r in rows} == {"Books to Scrape", "Quotes to Scrape"}
    first_book = next(r for r in rows if r["name_or_title"] == "Book One Title")
    assert first_book["price"] == "10.0" and first_book["rating"] == "3" and first_book["category"] == "Poetry"
    assert first_book["description"] == "A nice book."
    quote = next(r for r in rows if r["name_or_title"] == "Hello world.")
    assert quote["tags"] == "life;love" and quote["price"] == "" and quote["author"] == "Ann"
    assert json.load(open(tmp_path / "summary_report.json", encoding="utf-8"))["totals"]["final_record_count"] == 4


def test_source_failure_does_not_stop_other(server, tmp_path, monkeypatch):
    from scrapers.books_scraper import BooksScraper
    from scrapers.quotes_scraper import QuotesScraper
    from scrapers.base_scraper import create_session

    session = create_session(max_retries=0)
    monkeypatch.setattr(main, "BooksScraper", lambda **kw: BooksScraper(
        start_url=server + "/does-not-exist", session=session, **kw))     # first page 404
    monkeypatch.setattr(main, "QuotesScraper", lambda **kw: QuotesScraper(
        start_url=server + "/quotes/", session=session, **kw))
    summary = main.run_pipeline(main.parse_args(["--output-dir", str(tmp_path), "--delay", "0", "--skip-details"]))
    assert summary["sources"]["Books to Scrape"]["raw_collected"] == 0
    assert summary["sources"]["Books to Scrape"]["status"] == "failed"
    assert summary["sources"]["Quotes to Scrape"]["final"] == 2
