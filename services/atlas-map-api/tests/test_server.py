"""Smoke tests for atlas-map-api against the real audit/system-index.json."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_map_api.server import app


client = TestClient(app)


def test_root_lists_endpoints():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "atlas-map-api"
    assert body["subsystem_count"] > 0
    assert "/map/systems" in body["endpoints"]


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_systems():
    r = client.get("/map/systems")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    names = {s["name"] for s in body["items"]}
    # delta-kernel should always be there
    assert "delta-kernel" in names


def test_list_systems_filter_group():
    r = client.get("/map/systems?group=services")
    body = r.json()
    assert all(s["group"] == "services" for s in body["items"])


def test_get_system_delta_kernel():
    r = client.get("/map/systems/delta-kernel")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "delta-kernel"
    assert body["port"] == 3001
    assert isinstance(body["depends_on"], list)
    assert isinstance(body["depended_on_by"], list)


def test_get_system_404():
    r = client.get("/map/systems/__nonexistent__")
    assert r.status_code == 404


def test_locate_file_in_delta_kernel():
    r = client.get("/map/locate?file=services/delta-kernel/src/api/server.ts")
    body = r.json()
    assert body["system"] == "delta-kernel"
    assert body["match"] == "prefix"


def test_locate_unknown_file():
    r = client.get("/map/locate?file=this/does/not/exist.py")
    body = r.json()
    assert body["system"] is None


def test_neighbors_lattice():
    r = client.get("/map/neighbors/lattice?hops=2")
    assert r.status_code == 200
    body = r.json()
    assert body["root"] == "lattice"
    assert body["hops"] == 2
    assert "0" in body["by_distance"]
    assert "lattice" in body["by_distance"]["0"]


def test_path_lattice_to_delta_kernel():
    r = client.get("/map/path?from=lattice&to=delta-kernel")
    assert r.status_code == 200
    body = r.json()
    # lattice → delta-kernel is a hand-curated direct edge
    assert body["forward"] == ["lattice", "delta-kernel"]


def test_search_finds_delta():
    r = client.get("/map/search?q=delta&limit=5")
    body = r.json()
    names = [s["name"] for s in body["items"]]
    assert "delta-kernel" in names


def test_signals_includes_ports():
    r = client.get("/map/signals")
    body = r.json()
    ports = {p["name"]: p["port"] for p in body["ported"]}
    assert ports.get("delta-kernel") == 3001
    assert "autostart" in body


def test_viewer_shape_matches_window_services():
    r = client.get("/map/viewer?probe=false")
    assert r.status_code == 200
    body = r.json()
    assert body["probed"] is False
    svc = {s["name"]: s for s in body["services"]}
    assert "delta-kernel" in svc
    dk = svc["delta-kernel"]
    # exact window.SERVICES field set the viewer consumes
    for k in (
        "name", "group", "port", "running", "health", "state", "gov", "lang",
        "framework", "files", "loc", "deps_count", "in_autostart", "purpose",
        "entry_points",
    ):
        assert k in dk, f"missing viewer field: {k}"
    assert dk["port"] == 3001
    assert isinstance(body["edges"], list)
    assert {"from", "to"} <= set(body["edges"][0].keys())


def test_viewer_governance_and_health():
    r = client.get("/map/viewer?probe=false")
    body = r.json()
    svc = {s["name"]: s for s in body["services"]}
    # cognitive-sensor's triage arm is dormant per the loop trace — carried into the map
    cs = svc["cognitive-sensor"]
    assert cs["gov"]["automation"] == "dormant"
    assert "unscheduled" in cs["gov"]["note"].lower()
    # health is one of the three derived states for every service
    assert all(s["health"] in ("ok", "down", "idle") for s in body["services"])


def test_viewer_live_probe_returns_bool_running():
    r = client.get("/map/viewer?probe=true")
    assert r.status_code == 200
    body = r.json()
    assert body["probed"] is True
    assert all(isinstance(s["running"], bool) for s in body["services"])


def test_admin_reload():
    r = client.post("/admin/reload")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
