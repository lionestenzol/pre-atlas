"""Python docs as a queryable dictionary — port of conversation #78
"Python Documentation as Dictionary" (2025-03-09), Pre Atlas harvest pipeline.

Pipeline: PDF text -> SQLite rows (section, name, description, example) ->
substring search by function/module name. The original transcript also
sketched an OpenAI-backed natural-language query wrapper and an ipywidgets
UI on top of the same search_docs() call -- both omitted here since they
add a dependency (openai / ipywidgets) without adding new logic over the
plain SQL search underneath them.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def build_docs_db(db_path: str | Path, entries: list[tuple[str, str, str, str]]) -> None:
    """Create (or extend) the documentation table.

    entries: list of (section, name, description, example) tuples.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documentation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT,
                name TEXT,
                description TEXT,
                example TEXT
            )
            """
        )
        cursor.executemany(
            "INSERT INTO documentation (section, name, description, example) VALUES (?, ?, ?, ?)",
            entries,
        )
        conn.commit()
    finally:
        conn.close()


def search_docs(db_path: str | Path, term: str) -> list[tuple]:
    """Substring-search the documentation table by name."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM documentation WHERE name LIKE ?", (f"%{term}%",)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract full text from a PDF via PyMuPDF (fitz). Optional dependency --
    only imported here, not at module load, so the rest of this module works
    without PyMuPDF installed."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    return "\n".join(pages)
