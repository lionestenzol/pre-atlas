"""Intent classifier rules."""

from search_stack.router import (
    KIND_CODE,
    KIND_EXTRACT,
    KIND_FILE,
    KIND_GITHUB,
    KIND_WEB,
    classify,
)


def test_url_routes_to_extract():
    assert classify("https://example.com/docs") == KIND_EXTRACT
    assert classify("http://localhost:3070") == KIND_EXTRACT


def test_github_routes():
    assert classify("react hooks site:github.com") == KIND_GITHUB
    assert classify("repo:vercel/next.js") == KIND_GITHUB


def test_file_prefix():
    assert classify("path:tsconfig.json") == KIND_FILE
    assert classify("file:.env") == KIND_FILE


def test_code_prefix():
    assert classify("rg:def handle_") == KIND_CODE
    assert classify("fd:packet") == KIND_CODE
    assert classify("sg:async def $NAME") == KIND_CODE


def test_default_is_web():
    assert classify("how do react server components work") == KIND_WEB
    assert classify("best vector database 2026") == KIND_WEB


def test_explicit_kind_wins():
    assert classify("https://example.com", explicit_kind="web") == KIND_WEB
    assert classify("hello", explicit_kind="memory") == "memory"


def test_invalid_explicit_falls_back_to_inferred():
    assert classify("https://example.com", explicit_kind="bogus") == KIND_EXTRACT
