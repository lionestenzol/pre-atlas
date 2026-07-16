"""Tests for the free-text dispatch layer (/route, atlas_route) — the "librarian".

Ranking-correctness + gating assertions run against a SYNTHETIC fixture (two
controlled surfaces) via monkeypatch, so they don't drift with live overlay data.
A couple of endpoint-level smoke tests run against the real on-disk overlays to
prove the pilot triggers (code-recon, atlas-map-api's own `route` capability)
actually resolve end to end.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas_map_api import auth
from atlas_map_api import describe as d
from atlas_map_api import route as r
from atlas_map_api.server import app

client = TestClient(app)

BEARINGS = d.SurfaceOverlay(
    "bearings",
    "Deterministic orientation digest",
    (
        d.Capability(
            "digest", "Print today's orientation digest", "read", "public", 0,
            "python bearings.py", triggers=("where am i", "what did i do today", "catch me up"),
        ),
    ),
    kind="cli",
)

AUTOPILOT = d.SurfaceOverlay(
    "autopilot",
    "Deterministic fest orchestrator",
    (
        d.Capability(
            "status", "Show festival status", "read", "public", 0,
            "python orchestrator.py --status", triggers=("what's next", "festival status"),
        ),
        d.Capability(
            "run", "Execute next task", "write", "agent", 1,
            "python orchestrator.py", triggers=("run autopilot", "drive the festival forward"),
        ),
        d.Capability(
            "purge_all", "Wipe every festival", "write", "internal", 3,
            "python orchestrator.py --nuke", triggers=("catch me up",),  # deliberately colliding trigger
        ),
    ),
    kind="cli",
)

_OVERLAYS = {"bearings": BEARINGS, "autopilot": AUTOPILOT}


@pytest.fixture()
def fixture_registry(monkeypatch):
    monkeypatch.setattr(d, "described_surfaces", lambda repo_root: sorted(_OVERLAYS))
    monkeypatch.setattr(d, "load_overlay", lambda repo_root, surface: _OVERLAYS.get(surface))
    return _OVERLAYS


# ---- ranking correctness -------------------------------------------------------
def test_trigger_phrase_wins_a_confident_top_match(fixture_registry):
    result = r.route(Path("."), d.ROLES["agent"], "where am i", limit=5)
    assert result["count"] >= 1
    top = result["matches"][0]
    assert top["surface"] == "bearings" and top["capability"] == "digest"
    assert result["confident"] is True


def test_run_autopilot_matches_the_run_capability(fixture_registry):
    result = r.route(Path("."), d.ROLES["agent"], "run autopilot", limit=5)
    top = result["matches"][0]
    assert top["surface"] == "autopilot" and top["capability"] == "run"


def test_irrelevant_query_yields_no_matches(fixture_registry):
    # Measured noise floor for this fixture against a nonsense query tops out
    # ~41 under the trigger-weighted scheme — comfortably under MATCH_MIN_SCORE=55.
    result = r.route(Path("."), d.ROLES["agent"], "xkcd zzyzx quantum toaster", limit=5)
    assert result["count"] == 0 and result["matches"] == []


# ---- security property: never surfaces past clearance --------------------------
def test_agent_never_sees_internal_capability_even_with_matching_trigger(fixture_registry):
    # "catch me up" matches BOTH bearings.digest (public) and autopilot.purge_all
    # (internal, criticality 3, deliberately given a colliding trigger). An agent
    # role must never see purge_all surface here, mirroring what /describe(agent)
    # would show — the router can't leak more than describe already gates.
    result = r.route(Path("."), d.ROLES["agent"], "catch me up", limit=5)
    ids = {(m["surface"], m["capability"]) for m in result["matches"]}
    assert ("autopilot", "purge_all") not in ids
    assert ("bearings", "digest") in ids


def test_root_can_see_the_internal_capability_the_agent_cannot(fixture_registry):
    result = r.route(Path("."), d.ROLES["root"], "catch me up", limit=5)
    ids = {(m["surface"], m["capability"]) for m in result["matches"]}
    assert ("autopilot", "purge_all") in ids


# ---- confidence threshold: ambiguous ties surface as a shortlist ---------------
def test_ambiguous_query_is_not_confident(monkeypatch):
    # Two surfaces with an IDENTICAL label/trigger — a deterministic exact score
    # tie, rather than relying on WRatio nuance to produce ambiguity organically.
    tied = {
        "demo-a": d.SurfaceOverlay("demo-a", "", (
            d.Capability("go", "Do the thing", "read", "public", 0, "cmd-a", triggers=("do the thing please",)),
        ), kind="cli"),
        "demo-b": d.SurfaceOverlay("demo-b", "", (
            d.Capability("go", "Do the thing", "read", "public", 0, "cmd-b", triggers=("do the thing please",)),
        ), kind="cli"),
    }
    monkeypatch.setattr(d, "described_surfaces", lambda repo_root: sorted(tied))
    monkeypatch.setattr(d, "load_overlay", lambda repo_root, surface: tied.get(surface))
    result = r.route(Path("."), d.ROLES["agent"], "do the thing please", limit=5)
    assert result["count"] == 2
    assert result["matches"][0]["score"] == result["matches"][1]["score"]
    assert result["confident"] is False


# ---- endpoint-level smoke tests against real on-disk overlays ------------------
# code-recon.orient and atlas-map-api.route are both exposure="agent" — invisible
# to the default anon caller, same as /describe. Narrow the write token down to
# "agent" (mirrors test_describe.py's test_write_token_can_narrow_to_agent) so
# these smoke tests see what an agent caller actually would.
def _agent_headers() -> dict:
    return {"X-Atlas-Token": auth.current_token()}


def test_route_endpoint_resolves_code_recon_orient_trigger():
    r_ = client.get("/route?q=orient me on this repo&role=agent&limit=15", headers=_agent_headers())
    assert r_.status_code == 200
    body = r_.json()
    ids = {(m["surface"], m["capability"]) for m in body["matches"]}
    assert ("code-recon", "orient") in ids


def test_route_endpoint_dogfoods_its_own_route_capability():
    r_ = client.get("/route?q=which tool should i use for this&role=agent&limit=15", headers=_agent_headers())
    body = r_.json()
    ids = {(m["surface"], m["capability"]) for m in body["matches"]}
    assert ("atlas-map-api", "route") in ids


def test_run_autopilot_beats_unrelated_capability_at_full_corpus_scale():
    # Regression guard: the original merged-haystack scoring scored optogon's
    # UNRELATED "Start a path session and run the first turn" at 85 against
    # "run autopilot" — higher than autopilot's own capabilities (57-60) — purely
    # from incidental word/character overlap. The trigger-weighted scheme must
    # keep the curated exact-trigger match on top against the full live registry.
    r_ = client.get("/route?q=run autopilot&role=agent&limit=15", headers=_agent_headers())
    body = r_.json()
    assert body["matches"], "expected at least one match"
    assert body["matches"][0]["surface"] == "autopilot"
    assert body["matches"][0]["capability"] == "run"
    ids = {(m["surface"], m["capability"]) for m in body["matches"]}
    assert ("optogon", "session_start") not in ids


def test_route_endpoint_never_invokes_anything():
    # Purely a naming/ranking response — no `data`/`status` invocation envelope.
    body = client.get("/route?q=where am i").json()
    assert set(body.keys()) == {"query", "count", "confident", "matches"}
