from processing.cleaning import (clean_text, strip_quotes, clean_price, clean_rating,
                                 clean_tags, normalize_url, clean_book, clean_quote)


def test_clean_text():
    assert clean_text("  Hello \n World ") == "Hello World"
    assert clean_text("a\xa0b\t c") == "a b c"
    assert clean_text("   ") is None and clean_text(None) is None


def test_strip_quotes():
    assert strip_quotes("\u201cThe world.\u201d") == "The world."
    assert strip_quotes(None) is None


def test_clean_price():
    assert clean_price("\u00a351.77") == 51.77
    assert clean_price("\u00c2\u00a351.77") == 51.77      # mojibake variant
    assert clean_price("\u00a31,234.50") == 1234.50
    assert clean_price("free") is None and clean_price(None) is None


def test_clean_rating():
    assert clean_rating("star-rating Three") == 3
    assert clean_rating("Five") == 5
    assert clean_rating("star-rating") is None


def test_clean_tags():
    assert clean_tags(["Love", " books ", "love"]) == "books;love"
    assert clean_tags([]) is None


def test_normalize_url():
    assert normalize_url("/author/x", base="https://quotes.toscrape.com/page/2/") == "https://quotes.toscrape.com/author/x"
    assert normalize_url("ftp://x") is None and normalize_url("") is None


def test_clean_book_and_quote_shapes():
    book = clean_book({"source": "Books to Scrape", "title": " T ", "source_url": "https://x.com/b",
                       "price_raw": "\u00a35.00", "rating_raw": "star-rating Two", "scraped_at": "t"})
    assert book["price"] == 5.0 and book["rating"] == 2 and book["author"] is None
    quote = clean_quote({"source": "Quotes to Scrape", "text": "\u201cHi\u201d", "author": "A",
                         "tags_raw": ["b", "a"], "source_url": "https://x.com/", "scraped_at": "t"})
    assert quote["name_or_title"] == "Hi" and quote["tags"] == "a;b" and quote["price"] is None
