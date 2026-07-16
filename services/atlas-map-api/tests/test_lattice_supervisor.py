"""Tests for tools/lattice/supervisor.py -- the Seq 7 delta-kernel work-queue
REST client.

Hermetic: no real HTTP call, no real delta-kernel process. Mocks
urllib.request.urlopen to prove (1) the request/response shapes are built and
parsed correctly, (2) the fail-soft contract holds -- an unreachable or
non-APPROVED delta-kernel must never raise, only return None/False, since
supervision is additive and a lattice run must still complete without it, and
(3) the auth handshake -- GET /api/auth/token then Authorization: Bearer on
every POST -- found live-testing against a real running delta-kernel with an
.aegis-tenant-key on disk (CLAUDE.md: every /api/* route except /api/auth/token
requires it once that file exists). The first version of this module didn't
send the header at all and every call would have 403'd against a real
tenant-keyed instance; that's exactly the class of bug hermetic mocks alone
would not have caught, which is why this got run live before being called done.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch


def _load_lattice_module(name: str):
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


supervisor = _load_lattice_module("supervisor")


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _dispatcher(token: str | None, post_response: dict, captured: dict):
    """Routes the fake urlopen to a token response for the GET /api/auth/token
    call and the given post_response for everything else, recording both the
    POST body and headers so tests can assert on them."""

    def fake_urlopen(req, timeout):
        if req.full_url.endswith("/api/auth/token"):
            return _FakeResponse({"ok": True, "token": token})
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(post_response)

    return fake_urlopen


def test_register_job_sends_system_type_and_lattice_resume_metadata():
    captured: dict = {}
    fake = _dispatcher("tok-abc", {"status": "APPROVED", "job_id": "j-123"}, captured)

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        job_id = supervisor.register_job(
            "http://127.0.0.1:3001",
            thread_id="t1",
            pairs=[("code-recon", "find X")],
            db="lattice_runs.sqlite",
            max_turns=8,
            max_budget_usd=1.0,
            timeout_ms=120_000,
        )

    assert job_id == "j-123"
    assert captured["url"] == "http://127.0.0.1:3001/api/work/request"
    assert captured["body"]["type"] == "system"
    assert captured["body"]["timeout_ms"] == 120_000
    meta = captured["body"]["metadata"]
    assert meta["kind"] == "lattice_resume"
    assert meta["thread_id"] == "t1"
    assert meta["pairs"] == [["code-recon", "find X"]]
    assert meta["db"] == "lattice_runs.sqlite"
    assert meta["demo"] is False


def test_post_attaches_bearer_token_when_delta_kernel_has_a_tenant_key():
    captured: dict = {}
    fake = _dispatcher("tok-abc", {"status": "APPROVED", "job_id": "j-1"}, captured)

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        supervisor.register_job(
            "http://127.0.0.1:3001", thread_id="t1", pairs=None, db="x.sqlite",
            max_turns=8, max_budget_usd=1.0, timeout_ms=1000,
        )

    # urllib.Request lowercases/title-cases header keys internally as "Authorization"
    assert captured["headers"].get("Authorization") == "Bearer tok-abc"


def test_post_omits_bearer_header_in_dev_mode_with_no_tenant_key():
    captured: dict = {}
    fake = _dispatcher(None, {"status": "APPROVED", "job_id": "j-1"}, captured)

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        supervisor.register_job(
            "http://127.0.0.1:3001", thread_id="t1", pairs=None, db="x.sqlite",
            max_turns=8, max_budget_usd=1.0, timeout_ms=1000,
        )

    assert "Authorization" not in captured["headers"]


def test_register_job_returns_none_when_not_approved():
    fake = _dispatcher(None, {"status": "QUEUED", "job_id": "j-999"}, {})

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        job_id = supervisor.register_job(
            "http://127.0.0.1:3001", thread_id="t1", pairs=None, db="x.sqlite",
            max_turns=8, max_budget_usd=1.0, timeout_ms=1000,
        )

    assert job_id is None


def test_register_job_fails_soft_when_delta_kernel_unreachable():
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake_urlopen):
        job_id = supervisor.register_job(
            "http://127.0.0.1:3001", thread_id="t1", pairs=None, db="x.sqlite",
            max_turns=8, max_budget_usd=1.0, timeout_ms=1000,
        )

    assert job_id is None


def test_complete_job_reports_outcome_and_error():
    captured: dict = {}
    fake = _dispatcher(None, {"success": True}, captured)

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        ok = supervisor.complete_job("http://127.0.0.1:3001", "j-123", outcome="failed", error="boom")

    assert ok is True
    assert captured["body"] == {"job_id": "j-123", "outcome": "failed", "error": "boom"}


def test_complete_job_omits_error_key_when_none():
    captured: dict = {}
    fake = _dispatcher(None, {"success": True}, captured)

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        supervisor.complete_job("http://127.0.0.1:3001", "j-123", outcome="completed")

    assert "error" not in captured["body"]


def test_complete_job_fails_soft_on_malformed_response():
    fake = _dispatcher(None, {"not": "the expected shape"}, {})

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake):
        ok = supervisor.complete_job("http://127.0.0.1:3001", "j-123", outcome="completed")

    assert ok is False


def test_complete_job_fails_soft_when_unreachable():
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake_urlopen):
        ok = supervisor.complete_job("http://127.0.0.1:3001", "j-123", outcome="completed")

    assert ok is False


def test_fetch_token_fails_soft_when_delta_kernel_unreachable():
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    with patch.object(supervisor.urllib.request, "urlopen", side_effect=fake_urlopen):
        assert supervisor._fetch_token("http://127.0.0.1:3001") is None
