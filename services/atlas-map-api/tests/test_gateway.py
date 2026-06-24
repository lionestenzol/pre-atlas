"""Tests for the layer-3 call gateway (POST /call) — enforcement + URL building.

Enforcement paths (404/403/501/422) return before any network call, so they're
deterministic. The live proxy path is proven separately (manual curl vs a running
service); here we only assert the gateway's own logic.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_map_api import auth
from atlas_map_api import describe as d
from atlas_map_api import gateway
from atlas_map_api.loader import load_snapshot
from atlas_map_api.server import app

client = TestClient(app)


def _root() -> dict[str, str]:
    return {"X-Atlas-Token": auth.current_token()}


# ---- pure URL building --------------------------------------------------------
def test_parse_invoke():
    assert gateway.parse_invoke("POST /api/drop") == ("POST", "/api/drop")
    assert gateway.parse_invoke("/healthz") == ("GET", "/healthz")


def test_build_target_fills_path_params_and_query():
    method, url, body = gateway.build_target(
        "http://127.0.0.1:3073", "GET /api/dag/{dag_id}", {"dag_id": "d1", "verbose": "1"}
    )
    assert method == "GET"
    assert url == "http://127.0.0.1:3073/api/dag/d1?verbose=1"
    assert body == {}


def test_build_target_post_keeps_body():
    method, url, body = gateway.build_target("http://h:1", "POST /api/drop", {"text": "hi"})
    assert method == "POST" and url == "http://h:1/api/drop" and body == {"text": "hi"}


def test_resolve_base_url_prefers_launchjson_runtime_port():
    snap = load_snapshot()
    # triangulation got a launch.json entry @ 3074 (the stale snapshot says 3010/null)
    assert gateway.resolve_base_url(snap, "triangulation") == "http://127.0.0.1:3074"


# ---- enforcement (no network) -------------------------------------------------
def test_unknown_surface_404():
    r = client.post("/call", json={"surface": "nope", "capability": "x"})
    assert r.status_code == 404


def test_unknown_capability_404():
    r = client.post("/call", json={"surface": "delta-kernel", "capability": "nope"})
    assert r.status_code == 404


def test_capability_not_visible_to_anon_403():
    # set_state is internal — anon's form never shows it, so the gateway refuses.
    r = client.post("/call", json={"surface": "delta-kernel", "capability": "set_state"})
    assert r.status_code == 403


def test_write_capability_gated_501():
    # root CAN see droplist 'drop' (write), but writes are gated off by default.
    r = client.post("/call", json={"surface": "droplist", "capability": "drop", "args": {"text": "x"}}, headers=_root())
    assert r.status_code == 501


def test_non_http_surface_not_proxyable_422():
    snap = load_snapshot()
    cli_overlay = d.load_overlay(snap.repo_root, "atlas-cli")
    assert cli_overlay is not None and cli_overlay.kind == "cli"
    cap_id = cli_overlay.capabilities[0].id  # root can see it; kind=cli -> 422
    r = client.post("/call", json={"surface": "atlas-cli", "capability": cap_id}, headers=_root())
    assert r.status_code == 422


def test_visible_read_capability_passes_enforcement_then_proxies():
    # anon CAN see delta-kernel 'health' (public read). Enforcement passes; the
    # proxy then either reaches a running kernel (2xx) or reports it unreachable
    # (502) — both prove we got PAST the registry ACL to the network step.
    r = client.post("/call", json={"surface": "delta-kernel", "capability": "health"})
    assert r.status_code in (200, 502)
