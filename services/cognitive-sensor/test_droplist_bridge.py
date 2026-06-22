"""Acceptance for the triage -> DropList seam (droplist_bridge).

Run:  python test_droplist_bridge.py        (self-contained, no pytest needed)
  or: python -m pytest test_droplist_bridge.py -q
"""
from __future__ import annotations

import io
import json
from contextlib import contextmanager
from unittest import mock

import droplist_bridge as db


# ── pure logic ───────────────────────────────────────────────────────────────

def test_is_actionable_rejects_noise():
    for dead in ("", "none", "None", "NO-OP", "noop", "keep", None):
        assert db.is_actionable(dead) is False, dead
    for live in ("archive", "rotate key", "delete stale env"):
        assert db.is_actionable(live) is True, live


def test_build_raw_input_composes_and_collapses():
    assert db.build_raw_input("Stale .env", "rotate key", "exposed 90d") == \
        "Stale .env: rotate key -- exposed 90d"
    # missing rationale -> no trailing separator
    assert db.build_raw_input("Stale .env", "rotate key") == "Stale .env: rotate key"
    # missing title -> action stands alone
    assert db.build_raw_input("", "rotate key") == "rotate key"


# ── env-gating / dormant default ─────────────────────────────────────────────

def test_dormant_when_no_url(monkeypatch=None):
    with mock.patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("DROPLIST_DROP_URL", None)
        assert db.drop("t", "archive", "why") is None  # no url, no env -> dormant


def test_skips_non_actionable_even_with_url():
    assert db.drop("t", "none", "why", url="http://localhost:3073/api/drop") is None


# ── success path (mocked HTTP) ───────────────────────────────────────────────

@contextmanager
def _fake_urlopen(payload: dict, captured: dict):
    def _open(req, timeout=None):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        resp = io.BytesIO(json.dumps(payload).encode("utf-8"))
        resp.__enter__ = lambda self=resp: self
        resp.__exit__ = lambda self=resp, *a: False
        return resp
    with mock.patch("urllib.request.urlopen", _open):
        yield


def test_success_posts_rawinput_and_wraps_ok():
    captured: dict = {}
    intake_response = {"status": "secured", "delta_hash": "abc", "drop_id": "DROP-1"}
    with _fake_urlopen(intake_response, captured):
        out = db.drop("Stale .env", "rotate key", "exposed 90d",
                      url="http://localhost:3073/api/drop")
    assert out is not None and out["ok"] is True
    assert out["status"] == "secured" and out["drop_id"] == "DROP-1"
    # it spoke the intake contract: {"rawInput": "..."} to /api/drop
    assert captured["url"].endswith("/api/drop")
    assert captured["body"] == {"rawInput": "Stale .env: rotate key -- exposed 90d"}


# ── fail-soft contract ───────────────────────────────────────────────────────

def test_failsoft_returns_error_never_raises():
    import urllib.error

    def _boom(req, timeout=None):  # noqa: ANN001
        raise urllib.error.URLError("connection refused")

    with mock.patch("urllib.request.urlopen", _boom):
        out = db.drop("t", "archive", "why", url="http://127.0.0.1:9/api/drop")
    assert out is not None and out["ok"] is False
    assert "error" in out and out["raw_input"] == "t: archive -- why"


# ── self-contained runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {t.__name__}: {exc!r}")
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
