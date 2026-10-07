from processing.validation import validate_record


def book(**kw):
    rec = {"source": "Books to Scrape", "name_or_title": "T", "source_url": "https://x.com/b",
           "price": 10.0, "rating": 3, "author": None}
    rec.update(kw)
    return rec


def test_valid_book():
    assert validate_record(book()) == []


def test_valid_quote():
    q = {"source": "Quotes to Scrape", "name_or_title": "Q", "source_url": "https://x.com", "author": "A",
         "price": None, "rating": None}
    assert validate_record(q) == []


def test_each_rule():
    assert "unknown_source" in validate_record(book(source="Other"))
    assert "missing_name" in validate_record(book(name_or_title=None))
    assert "invalid_url" in validate_record(book(source_url="nope"))
    assert "invalid_price" in validate_record(book(price=-1))
    assert "invalid_rating" in validate_record(book(rating=9))
    assert "missing_price" in validate_record(book(price=None))
    assert "missing_author" in validate_record({"source": "Quotes to Scrape", "name_or_title": "Q",
                                                "source_url": "https://x.com", "author": None})


def test_multiple_reasons_reported():
    assert set(validate_record(book(name_or_title="", source_url=None))) == {"missing_name", "invalid_url"}
