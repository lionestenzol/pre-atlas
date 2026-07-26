"""Task B acceptance: the X-Atlas-Token guard on DropList's write API.

The behavior suites (test_markoff, test_intake) override the guard to a no-op so
they can keep asserting graph behavior. THIS file does the opposite — it forces
the real guard live (popping any override another module set) and proves:

  - an unauthenticated write POST is rejected 401 (drop / complete / reopen)
  - the server-side Anthropic proxy is rejected unauthenticated
  - a wrong token is rejected
  - a request carrying the CORRECT token passes the guard and reaches the
    handler (404 dag-not-found, not 401)
  - GET reads are NOT guarded — the front door + read API stay public

See DROPLIST_SHIP_SPEC_2026-06-25.md Task B and droplist/auth.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from droplist import auth
from droplist.server import app


@pytest.fixture(autouse=True)
def _live_guard():
    """Force the real guard for this module, regardless of overrides set by other
    test modules (dependency_overrides is global on the shared app object)."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(auth.require_write_token, None)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


client = TestClient(app)


def test_unauth_drop_rejected():
    r = client.post("/api/drop", json={"raw": "buy milk"})
    assert r.status_code in (401, 403), r.text


def test_unauth_complete_rejected():
    r = client.post("/api/dag/DAG-X/node/N1/complete", json={})
    assert r.status_code in (401, 403), r.text


def test_unauth_reopen_rejected():
    r = client.post("/api/dag/DAG-X/node/N1/reopen")
    assert r.status_code in (401, 403), r.text


def test_unauth_anthropic_proxy_rejected():
    r = client.post("/api/ai/anthropic", json={"model": "x", "messages": []})
    assert r.status_code in (401, 403), r.text


def test_bad_token_rejected():
    r = client.post("/api/drop", json={"raw": "x"}, headers={"X-Atlas-Token": "nope"})
    assert r.status_code in (401, 403), r.text


def test_valid_token_passes_guard():
    # A correct token reaches the handler; a non-existent dag then yields 404,
    # proving the request passed auth (it would be 401 otherwise).
    tok = auth.current_token()
    r = client.post(
        "/api/dag/DAG-DOES-NOT-EXIST/node/N1/complete",
        json={},
        headers={"X-Atlas-Token": tok},
    )
    assert r.status_code == 404, r.text


def test_reads_stay_open():
    # GET endpoints carry no guard — the read API + UI front door stay public.
    assert client.get("/api/now").status_code not in (401, 403)
