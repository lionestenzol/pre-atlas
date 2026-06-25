"""Phase 2 wire — retrieval.py ↔ services/search-stack.

Uses a tiny stdlib HTTP server to stand in for search-stack so the test stays
hermetic. No real network, no external service required.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from droplist import retrieval


@pytest.fixture()
def fake_search_stack(monkeypatch):
    """Spawn a localhost server that mimics /search; teardown after test."""
    captured: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib API
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8")
            captured["payload"] = json.loads(body)
            response = {
                "kind": "web",
                "results": [
                    {
                        "title": "React Server Components",
                        "url": "https://react.dev/rsc",
                        "snippet": "RSC overview from react.dev",
                        "score": 0.92,
                        "source": "exa",
                        "kind": "web",
                    },
                    {
                        "title": "Next.js docs on RSC",
                        "url": "https://nextjs.org/docs/rsc",
                        "snippet": "Next.js implementation guide",
                        "score": 0.84,
                        "source": "tavily",
                        "kind": "web",
                    },
                ],
                "providers_used": ["exa", "tavily"],
                "providers_failed": [],
                "n": 2,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def log_message(self, *_args, **_kwargs):
            pass  # silence test output

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SEARCH_STACK_URL", f"http://127.0.0.1:{port}/search")

    yield captured

    server.shutdown()


def test_retrieve_external_returns_snippet_shape(fake_search_stack):
    hits = retrieval.retrieve_external("react server components", kind="web", k=5)
    assert len(hits) == 2
    for h in hits:
        assert set(h.keys()) >= {"source", "snippet", "relevance", "type", "domain"}
        assert h["type"] == "external"
    assert hits[0]["relevance"] == 0.92
    assert fake_search_stack["payload"]["q"] == "react server components"


def test_retrieve_external_returns_empty_on_error(monkeypatch):
    monkeypatch.setenv("SEARCH_STACK_URL", "http://127.0.0.1:1/search")  # nothing listens on :1
    hits = retrieval.retrieve_external("anything", kind="web", k=5, timeout=1.0)
    assert hits == []


def test_retrieve_external_empty_query(fake_search_stack):
    assert retrieval.retrieve_external("", k=5) == []
    assert retrieval.retrieve_external("   ", k=5) == []


def test_retrieve_with_external_gated_by_env(monkeypatch, fake_search_stack):
    """Without DROPLIST_EXTERNAL_SEARCH=1, retrieve_with_external == retrieve."""
    monkeypatch.delenv("DROPLIST_EXTERNAL_SEARCH", raising=False)
    prior = [
        {"drop_id": "drop_001", "normalized_input": "react server components",
         "type": "research", "domain": "frontend"},
    ]
    out = retrieval.retrieve_with_external("react server components", prior, k=5)
    # all results should be internal (drop_001), no external hits
    assert all(h.get("type") != "external" for h in out)
    assert "payload" not in fake_search_stack  # server not called


def test_retrieve_with_external_merges_when_enabled(monkeypatch, fake_search_stack):
    monkeypatch.setenv("DROPLIST_EXTERNAL_SEARCH", "1")
    prior = [
        {"drop_id": "drop_001", "normalized_input": "react server components",
         "type": "research", "domain": "frontend"},
    ]
    out = retrieval.retrieve_with_external("react server components", prior, k=5)
    sources = {h["source"] for h in out}
    types = {h["type"] for h in out}
    assert "drop_001" in sources  # internal hit
    assert "external" in types     # external hits merged
    assert len([h for h in out if h.get("type") == "external"]) == 2


def test_retrieve_with_external_dedups_overlapping_source(monkeypatch, fake_search_stack):
    monkeypatch.setenv("DROPLIST_EXTERNAL_SEARCH", "1")
    prior = [
        {"drop_id": "https://react.dev/rsc", "normalized_input": "react server components",
         "type": "research", "domain": "frontend"},
    ]
    out = retrieval.retrieve_with_external("react server components", prior, k=5)
    rsc_url_hits = [h for h in out if h["source"] == "https://react.dev/rsc"]
    assert len(rsc_url_hits) == 1  # internal wins, external dropped


def test_internal_retrieve_still_works_unchanged():
    prior = [
        {"drop_id": "drop_a", "normalized_input": "build the search stack today",
         "type": "build", "domain": "tools"},
        {"drop_id": "drop_b", "normalized_input": "unrelated grocery list",
         "type": "admin", "domain": "home"},
    ]
    out = retrieval.retrieve("search stack", prior, k=3)
    assert len(out) == 1
    assert out[0]["source"] == "drop_a"
    assert out[0]["type"] == "build"
