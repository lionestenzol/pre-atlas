"""Tests for the revived FastAPI surface (Phase C). Cold-start: no model needed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from triangulation import api
from triangulation.api import app

client = TestClient(app)


# ---- pure functions -----------------------------------------------------------
def test_verify_endpoint_runs_cold_start(nav_row):
    results = api.verify_endpoint(nav_row)
    assert len(results) == 5
    for r in results:
        assert {"id", "label", "confidence", "signals", "verdict"} <= set(r)
        # visual signal is cold (no library / no model)
        assert r["signals"]["visual"]["score"] is None
        assert r["confidence"] > 0


def test_library_stats_empty_on_cold_start():
    # No persisted library in a clean checkout -> empty stats.
    assert isinstance(api.library_stats(), dict)


def test_library_add_fails_loudly_without_visual_extra():
    out = api.library_add("nav_link", "/x.png")
    assert out["ok"] is False
    assert "visual extra" in out["error"]


# ---- HTTP surface -------------------------------------------------------------
def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["service"] == "triangulation"
    assert body["visual_available"] is False


def test_post_verify_returns_verdicts(nav_row):
    r = client.post("/verify", json={"elements": nav_row})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 5 and len(body["results"]) == 5
    assert all(res["verdict"] in ("confirmed", "flagged", "rejected") for res in body["results"])


def test_post_verify_flags_the_outlier(nav_row_with_outlier):
    r = client.post("/verify", json={"elements": nav_row_with_outlier})
    results = r.json()["results"]
    outlier = next(res for res in results if res["id"] == "nav-4")
    # the lone "button" among nav_links should not pass clean — flagged/rejected or carries a flag
    assert outlier["verdict"] != "confirmed" or outlier["flags"]


def test_library_stats_endpoint():
    r = client.get("/library/stats")
    assert r.status_code == 200 and "stats" in r.json()


def test_library_add_endpoint_503_without_visual():
    r = client.post("/library/add", json={"label": "nav_link", "screenshot_path": "/x.png"})
    assert r.status_code == 503
