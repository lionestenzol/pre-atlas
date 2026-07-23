import tempfile
from pathlib import Path

from docs_dictionary import build_docs_db, search_docs


def test_build_and_search():
    entries = [
        ("Functions", "print", "Outputs text to console", "print('Hello, World!')"),
        ("Modules", "os", "Provides functions to interact with the OS", "import os\nos.listdir()"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "docs.db"
        build_docs_db(db_path, entries)

        results = search_docs(db_path, "print")

        assert len(results) == 1
        assert results[0][2] == "print"
        assert results[0][3] == "Outputs text to console"


def test_search_no_match_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "docs.db"
        build_docs_db(db_path, [("Functions", "print", "desc", "example")])

        assert search_docs(db_path, "nonexistent_function") == []


def test_build_docs_db_is_idempotent_across_calls():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "docs.db"
        build_docs_db(db_path, [("Functions", "print", "desc", "example")])
        build_docs_db(db_path, [("Functions", "len", "desc2", "example2")])

        assert len(search_docs(db_path, "print")) == 1
        assert len(search_docs(db_path, "len")) == 1
