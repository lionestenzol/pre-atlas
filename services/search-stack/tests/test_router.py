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


def test_research_prefix():
    assert classify("arxiv:transformer") == "research"
    assert classify("paper:attention is all you need") == "research"
    assert classify("doi:10.1145/3133957") == "research"


def test_social_prefix():
    assert classify("reddit:claude code") == "social"
    assert classify("hn:react server components") == "social"


def test_news_prefix():
    assert classify("news:anthropic dev day") == "news"


def test_legal_prefix():
    assert classify("sec:AAPL 10-K") == "legal"
    assert classify("court:roe v wade") == "legal"


def test_data_prefix():
    assert classify("dataset:US population") == "data"
    assert classify("fred:GDP") == "data"


def test_local_prefix():
    assert classify("place:Brooklyn pizza") == "local"
    assert classify("yelp:coffee austin") == "local"


def test_multimedia_prefix():
    assert classify("video:claude tutorial") == "multimedia"
    assert classify("yt:react server components") == "multimedia"


def test_product_prefix():
    assert classify("amazon:logitech mx master") == "product"
    assert classify("asin:B07GBZ4Q68") == "product"
