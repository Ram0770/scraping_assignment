from processing.deduplication import find_duplicates

BASE = {"source": "Books to Scrape", "author": None}


def test_duplicates_ignore_case_and_spaces():
    records = [{**BASE, "name_or_title": "Example Book Title"},
               {**BASE, "name_or_title": "  Example Book Title "},
               {**BASE, "name_or_title": "EXAMPLE BOOK TITLE"}]
    unique, dupes = find_duplicates(records)
    assert len(unique) == 1 and len(dupes) == 2


def test_punctuation_ignored():
    unique, dupes = find_duplicates([{**BASE, "name_or_title": "It's a Book!"}, {**BASE, "name_or_title": "its a book"}])
    assert len(unique) == 1 and len(dupes) == 1


def test_quotes_use_author_and_first_50_chars():
    q = {"source": "Quotes to Scrape", "author": "Ann", "name_or_title": "x" * 80}
    q2 = {**q, "name_or_title": "x" * 50 + "different ending"}
    other_author = {**q, "author": "Bob"}
    unique, dupes = find_duplicates([q, q2, other_author])
    assert len(unique) == 2 and len(dupes) == 1


def test_same_title_different_source_is_not_duplicate():
    a = {"source": "Books to Scrape", "author": None, "name_or_title": "Same"}
    b = {"source": "Quotes to Scrape", "author": "A", "name_or_title": "Same"}
    assert len(find_duplicates([a, b])[0]) == 2
