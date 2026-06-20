"""Smoke tests for atlas-map-api against the real audit/system-index.json."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas_map_api import auth
from atlas_map_api.server import app


client = TestClient(app)


def _auth() -> dict[str, str]:
    """Header carrying the valid write token for state-changing POSTs."""
    return {"X-Atlas-Token": auth.current_token()}


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


def test_launch_allowlist_loads():
    from atlas_map_api import launcher
    from atlas_map_api.loader import load_snapshot
    root = load_snapshot().repo_root
    cfgs = launcher.load_launch_configs(root)
    assert len(cfgs) > 0
    assert all("name" in c for c in cfgs)


def test_config_resolves_by_port():
    from atlas_map_api import launcher
    from atlas_map_api.loader import load_snapshot
    root = load_snapshot().repo_root
    cfg = launcher.config_for_port(root, 3001)  # delta-kernel's API port
    assert cfg is not None
    assert cfg.get("runtimeExecutable")


def test_start_unknown_subsystem_404():
    r = client.post("/map/start/__nonexistent__", headers=_auth())
    assert r.status_code == 404


def test_start_no_port_is_422_not_spawn():
    # cognitive-sensor has no port → cannot be started; must 422, never spawn
    r = client.post("/map/start/cognitive-sensor", headers=_auth())
    assert r.status_code == 422


def test_stop_requires_launch_config():
    # cognitive-sensor has no port / no launch config → stop must 422, not kill
    r = client.post("/map/stop/cognitive-sensor", headers=_auth())
    assert r.status_code == 422


def test_stop_refuses_self_port():
    from atlas_map_api import launcher
    res = launcher.stop_on_port(launcher.SELF_PORT)
    assert res["ok"] is False
    assert "itself" in res["error"]


def test_start_is_idempotent_when_running(monkeypatch):
    from atlas_map_api import launcher
    from atlas_map_api.loader import load_snapshot
    root = load_snapshot().repo_root
    cfg = launcher.config_for_port(root, 3001)
    monkeypatch.setattr(launcher, "port_alive", lambda *a, **k: True)
    # Popen must NOT be called when the port is already alive
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("spawned while running")))
    res = launcher.start_from_config(cfg, root)
    assert res["started"] is False
    assert res["reason"] == "already running"


def test_start_spawns_argv_without_shell(monkeypatch):
    from atlas_map_api import launcher
    from atlas_map_api.loader import load_snapshot
    root = load_snapshot().repo_root
    cfg = launcher.config_for_port(root, 3001)
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

    monkeypatch.setattr(launcher, "port_alive", lambda *a, **k: False)
    monkeypatch.setattr(launcher, "_resolve_exe", lambda exe: exe)  # pretend resolvable
    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)
    res = launcher.start_from_config(cfg, root)
    assert res["started"] is True
    assert isinstance(captured["cmd"], list)  # argv, never a string
    assert captured["kwargs"]["shell"] is False


def test_items_backbone_aggregates_sources():
    r = client.get("/items")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 0
    assert isinstance(body["by_source"], dict)
    # every item carries the one unified shape
    for it in body["items"][:50]:
        assert set(it.keys()) >= {"id", "source", "kind", "title", "status", "updated"}
        assert it["source"] in ("droplist", "cycleboard", "inpact")


def test_items_source_filter():
    r = client.get("/items?source=inpact")
    body = r.json()
    assert all(it["source"] == "inpact" for it in body["items"])


def test_parse_backbone_id():
    from atlas_map_api import items as ib
    assert ib.parse_backbone_id("bb:droplist:DAG-1") == ("droplist", "DAG-1")
    assert ib.parse_backbone_id("garbage") == (None, None)
    assert ib.parse_backbone_id("bb:droplist:") == (None, None)


def test_write_through_droplist_preserves_fields(tmp_path):
    import json
    from atlas_map_api import items as ib
    dags = tmp_path / "services" / "droplist" / "data" / "dags"
    dags.mkdir(parents=True)
    pkt = dags / "DAG-test.json"
    pkt.write_text(json.dumps({"dag_id": "DAG-test", "goal": "feed goat",
                               "status": "needs_human", "nodes": [1, 2]}), encoding="utf-8")
    res = ib.set_item_status(tmp_path, "bb:droplist:DAG-test", "done")
    assert res["ok"] is True
    assert res["old_status"] == "needs_human" and res["new_status"] == "done"
    after = json.loads(pkt.read_text(encoding="utf-8"))
    assert after["status"] == "done"
    assert after["goal"] == "feed goat" and after["nodes"] == [1, 2]  # untouched
    assert "updated_at" in after
    assert (dags / "DAG-test.json.bak").is_file()  # backup taken before mutate


def test_write_through_rejects_nondroplist(tmp_path):
    from atlas_map_api import items as ib
    res = ib.set_item_status(tmp_path, "bb:cycleboard:abc", "done")
    assert res["ok"] is False and "not supported" in res["error"]


def test_write_through_rejects_bad_status(tmp_path):
    from atlas_map_api import items as ib
    assert ib.set_item_status(tmp_path, "bb:droplist:DAG-x", "")["ok"] is False
    assert ib.set_item_status(tmp_path, "bb:droplist:DAG-x", "x" * 99)["ok"] is False


def test_write_through_rejects_path_traversal(tmp_path):
    from atlas_map_api import items as ib
    # native id with path separators / .. must be refused, never reach the filesystem
    for evil in ("bb:droplist:../../../../etc/passwd", "bb:droplist:..\\..\\x", "bb:droplist:a/b"):
        res = ib.set_item_status(tmp_path, evil, "done")
        assert res["ok"] is False, evil


def test_status_endpoint_rejects_nondroplist():
    r = client.post("/items/bb:cycleboard:abc/status", json={"status": "done"}, headers=_auth())
    assert r.status_code == 422


def test_admin_reload():
    r = client.post("/admin/reload", headers=_auth())
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------- write-token guard (X-Atlas-Token) ----------

# Every state-changing POST must be guarded; reads stay open. Parametrized so a
# new POST endpoint added without a token gate fails this test loudly.
_GUARDED_POSTS = [
    ("/admin/reload", None),
    ("/map/start/delta-kernel", None),
    ("/map/stop/delta-kernel", None),
    ("/map/restart/delta-kernel", None),
    ("/items/bb:droplist:DAG-x/status", {"status": "done"}),
]


@pytest.mark.parametrize("path,body", _GUARDED_POSTS)
def test_post_without_token_is_401(path, body):
    r = client.post(path, json=body) if body is not None else client.post(path)
    assert r.status_code == 401, f"{path} should require X-Atlas-Token"


@pytest.mark.parametrize("path,body", _GUARDED_POSTS)
def test_post_with_bad_token_is_401(path, body):
    headers = {"X-Atlas-Token": "not-the-real-token"}
    r = client.post(path, json=body, headers=headers) if body is not None else client.post(path, headers=headers)
    assert r.status_code == 401, f"{path} should reject a wrong token"


def test_post_with_valid_token_passes_guard():
    # A wrong-shaped item still gets past the auth gate (422 from the handler),
    # proving the valid token is accepted rather than 401'd.
    r = client.post("/items/bb:cycleboard:abc/status", json={"status": "done"}, headers=_auth())
    assert r.status_code == 422  # handler-level rejection, NOT 401


def test_write_token_handout_endpoint_is_open_and_matches():
    # GET handout has no auth (browser bootstrap) and returns the active token.
    r = client.get("/admin/write-token")
    assert r.status_code == 200
    assert r.json()["token"] == auth.current_token()


def test_load_or_create_token_is_idempotent(tmp_path):
    t1 = auth.load_or_create_token(tmp_path)
    t2 = auth.load_or_create_token(tmp_path)
    assert t1 == t2
    assert (tmp_path / auth.TOKEN_FILENAME).is_file()


def test_token_env_var_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setenv(auth.TOKEN_ENV, "env-supplied-token")
    assert auth.load_or_create_token(tmp_path) == "env-supplied-token"
    # env wins → no file written
    assert not (tmp_path / auth.TOKEN_FILENAME).is_file()


def test_workflow_returns_dag(tmp_path):
    import json
    from atlas_map_api import items as ib
    dags = tmp_path / "services" / "droplist" / "data" / "dags"
    dags.mkdir(parents=True)
    (dags / "DAG-w.json").write_text(json.dumps({"dag_id": "DAG-w", "goal": "g", "status": "open",
        "nodes": [{"id": "N1", "title": "a", "status": "done", "depends_on": "[]"},
                  {"id": "N2", "title": "b", "status": "blocked", "depends_on": "['N1']"}]}), encoding="utf-8")
    wf = ib.get_workflow(tmp_path, "bb:droplist:DAG-w")
    assert wf["ok"] and len(wf["nodes"]) == 2
    assert {"from": "N1", "to": "N2"} in wf["edges"]


def test_workflow_rejects_nondroplist(tmp_path):
    from atlas_map_api import items as ib
    assert ib.get_workflow(tmp_path, "bb:cycleboard:81")["ok"] is False


def test_launch_requires_token():
    assert client.post("/map/launch/lattice").status_code == 401


def test_launch_unknown_name_404():
    assert client.post("/map/launch/__nope__", headers=_auth()).status_code == 404
