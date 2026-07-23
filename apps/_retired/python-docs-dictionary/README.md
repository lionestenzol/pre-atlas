# Python Docs Dictionary

Extracted from conversation #78 "Python Documentation as Dictionary" (2025-03-09), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/78_python-documentation-as-dictionary/`), verdict MINE, decided 2026-04-21.

## What this is

A PDF-to-SQLite-to-search pipeline: extract text from a documentation PDF (`extract_pdf_text`, via PyMuPDF), store parsed entries as rows (`build_docs_db`), and substring-search them by name (`search_docs`). Covered by `test_docs_dictionary.py` (3/3 passing).

## What was left out

The original thread also sketched an OpenAI-backed natural-language wrapper (`query_python_docs`) and an ipywidgets search box on top of the same `search_docs()` call. Both are thin UI/LLM shells over the SQL search underneath — omitted here since they add dependencies (`openai`, `ipywidgets`) without adding logic, and the note said "not duplicative of code-converter — adjacent project worth capturing," not "wire this into a chat UI." If a natural-language front end is wanted later, it slots directly onto `search_docs()`.

## Run the tests

```
python -m pytest test_docs_dictionary.py -v
```
