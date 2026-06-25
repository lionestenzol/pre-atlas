"""Tests for the layer-3 call gateway (POST /call), incl. post-review hardening.

Enforcement paths return before any network/exec, so they're deterministic. A
reached invocation returns the normalized envelope as HTTP 200. The live
proxy/exec paths are proven separately (manual curl vs a running service).
"""

from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient

from atlas_map_api import auth
from atlas_map_api import describe as d
from atlas_map_api import gateway
from atlas_map_api.loader import load_snapshot
from atlas_map_api.server import app

client = TestClient(app)


def _root() -> dict[str, str]:
    return {"X-Atlas-Token": auth.current_token()}


# ---- URL building + path-traversal confinement (HIGH fix) ---------------------
def test_parse_invoke():
    assert gateway.parse_invoke("POST /api/drop") == ("POST", "/api/drop")
    assert gateway.parse_invoke("/healthz") == ("GET", "/healthz")


def test_build_target_query_for_leftover_args():
    method, url, body = gateway.build_target("http://h:1", "GET /api/packets", {"limit": "5"})
    assert method == "GET" and url == "http://h:1/api/packets?limit=5" and body == {}


def test_build_target_path_param_traversal_is_confined():
    # '../../admin/reload' must NOT escape the /api/dag/ segment: the slashes are
    # percent-encoded so httpx can't normalize a parent-dir traversal.
    _, url, _ = gateway.build_target("http://127.0.0.1:3073", "GET /api/dag/{dag_id}", {"dag_id": "../../admin/reload"})
    assert "/admin/reload" not in url
    assert url.startswith("http://127.0.0.1:3073/api/dag/")
    assert "%2F" in url  # slashes encoded -> single confined segment


def test_build_target_path_param_cannot_open_query():
    _, url, _ = gateway.build_target("http://h:1", "GET /entity/{name}", {"name": "x?admin=1"})
    assert "?admin=1" not in url and "?" not in url  # the '?' is percent-encoded


def test_resolve_base_url_prefers_launchjson_runtime_port():
    # triangulation's launch.json runtime port (moved 3074->3075 to clear the
    # droplist-ui collision) is preferred over the snapshot's stale 3010.
    assert gateway.resolve_base_url(load_snapshot(), "triangulation") == "http://127.0.0.1:3075"


# ---- argv building (cli hardening) --------------------------------------------
def test_build_argv_adds_end_of_options_sentinel():
    argv, err = gateway.build_argv("atlas where", {"limit": "5"})
    assert err is None and argv == ["atlas", "where", "--", "--limit", "5"]


def test_build_argv_rejects_shell_metacharacters():
    for bad in [{"x": "a; rm -rf /"}, {"x": "$(whoami)"}, {"x": "a`b`"}, {"x": "a|b"}]:
        argv, err = gateway.build_argv("atlas where", bad)
        assert err is not None and argv == []


def test_build_argv_rejects_leading_dash_values():
    for bad in [{"x": "-rf"}, {"x": "--evil-flag"}]:
        _, err = gateway.build_argv("atlas where", bad)
        assert err is not None


def test_build_argv_caps_size():
    assert gateway.build_argv("atlas where", {"x": "y" * 9999})[1] is not None
    assert gateway.build_argv("atlas where", {f"k{i}": "1" for i in range(99)})[1] is not None


# ---- write determination uses the VERB, not just the label (HIGH fix) ---------
def test_post_labeled_read_is_still_treated_as_write():
    snap = load_snapshot()
    verify = next(c for c in d.load_overlay(snap.repo_root, "triangulation").capabilities if c.id == "verify")
    assert verify.direction == "read" and verify.invoke.startswith("POST")
    assert gateway.is_write("http", verify) is True  # verb is ground truth
    health = next(c for c in d.load_overlay(snap.repo_root, "triangulation").capabilities if c.id == "healthz")
    assert gateway.is_write("http", health) is False


# ---- enforcement --------------------------------------------------------------
def test_unknown_surface_404():
    assert client.post("/call", json={"surface": "nope", "capability": "x"}).status_code == 404


def test_surface_name_traversal_blocked_404():
    assert client.post("/call", json={"surface": "../../etc", "capability": "x"}).status_code == 404


def test_unknown_capability_404():
    assert client.post("/call", json={"surface": "delta-kernel", "capability": "nope"}).status_code == 404


def test_anon_cannot_invoke_internal_403():
    assert client.post("/call", json={"surface": "delta-kernel", "capability": "set_state"}).status_code == 403


def test_undeclared_args_rejected_400():
    # 'evil' is not a declared param of droplist 'drop' (needs: ['text']).
    r = client.post("/call", json={"surface": "droplist", "capability": "drop", "args": {"text": "x", "evil": "1"}}, headers=_root())
    assert r.status_code == 400


def test_writes_gated_off_by_default_501():
    assert gateway.WRITES_ENABLED is False
    r = client.post("/call", json={"surface": "droplist", "capability": "drop", "args": {"text": "x"}}, headers=_root())
    assert r.status_code == 501


def test_cli_invocation_gated_off_501():
    snap = load_snapshot()
    cli = d.load_overlay(snap.repo_root, "atlas-cli")
    assert cli is not None and cli.kind == "cli"
    cap = next(c for c in cli.capabilities if c.direction == "read")  # read -> hits the cli gate, not the write gate
    assert client.post("/call", json={"surface": "atlas-cli", "capability": cap.id}, headers=_root()).status_code == 501


# ---- reached invocation -> normalized envelope --------------------------------
def test_read_capability_returns_envelope():
    r = client.post("/call", json={"surface": "delta-kernel", "capability": "health"})
    assert r.status_code == 200
    body = r.json()
    assert {"ok", "code", "surface", "capability", "kind", "status", "data", "error", "meta"} <= set(body)
    assert body["kind"] == "http"


def test_authorized_write_with_flag_reaches_invocation(monkeypatch):
    monkeypatch.setattr(gateway, "WRITES_ENABLED", True)
    r = client.post("/call", json={"surface": "droplist", "capability": "drop", "args": {"text": "x"}}, headers=_root())
    assert r.status_code == 200
    assert r.json()["kind"] == "http" and r.json()["capability"] == "drop"


# ---- mutating proxied calls forward the shared secret (one-token trust domain) ---
def _capture_proxy(monkeypatch) -> dict:
    """Patch httpx so _invoke_http hits no network; record the outgoing request's
    verb + headers for both the GET and the request() (mutating) paths."""
    seen: dict = {}

    async def fake_request(self, method, url, **kwargs):
        seen["method"], seen["headers"] = method, kwargs.get("headers")
        return httpx.Response(200, json={"ok": True})

    async def fake_get(self, url, **kwargs):
        seen["method"], seen["headers"] = "GET", kwargs.get("headers")
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return seen


def test_mutating_proxied_call_forwards_shared_secret(monkeypatch):
    # Without the X-Atlas-Token header a proxied write 401s once droplist's guard is
    # live (PR #25). The gateway must forward the root token for mutating verbs.
    snap = load_snapshot()
    seen = _capture_proxy(monkeypatch)
    drop = next(c for c in d.load_overlay(snap.repo_root, "droplist").capabilities if c.id == "drop")
    res = asyncio.run(gateway._invoke_http(snap, "droplist", drop, d.resolve_role("root"), {"text": "x"}))
    assert seen["method"] == "POST"
    assert seen["headers"] == {"X-Atlas-Token": auth.current_token()}
    assert res["ok"] is True


def test_read_proxied_call_carries_no_token(monkeypatch):
    # Reads stay open end-to-end — a GET must NOT carry the write secret.
    snap = load_snapshot()
    seen = _capture_proxy(monkeypatch)
    health = next(c for c in d.load_overlay(snap.repo_root, "delta-kernel").capabilities if c.id == "health")
    asyncio.run(gateway._invoke_http(snap, "delta-kernel", health, d.resolve_role("anon"), None))
    assert seen["method"] == "GET"
    assert seen["headers"] is None


def test_low_clearance_meta_does_not_leak_resolved_url():
    # anon reads delta-kernel health -> meta carries the DECLARED invoke, not the host:port URL.
    body = client.post("/call", json={"surface": "delta-kernel", "capability": "health"}).json()
    assert body["meta"].get("invoke") == "GET /api/health"


# ---- per-surface write-scoped tokens ------------------------------------------
def test_write_scoped_token_allows_in_scope_blocks_out_of_scope(monkeypatch):
    monkeypatch.setattr(gateway, "WRITES_ENABLED", True)
    monkeypatch.setattr(auth, "_role_tokens", {"scoped-tok": {"role": "agent", "write_surfaces": ["droplist"]}})
    h = {"X-Atlas-Token": "scoped-tok"}
    # in-scope write -> reaches invocation
    r_in = client.post("/call", json={"surface": "droplist", "capability": "drop", "args": {"text": "x"}}, headers=h)
    assert r_in.status_code == 200 and r_in.json()["kind"] == "http"
    # out-of-scope write (same agent role can SEE it, but token isn't scoped to it) -> 403
    r_out = client.post("/call", json={"surface": "delta-kernel", "capability": "emit_signal", "args": {"signal": "x"}}, headers=h)
    assert r_out.status_code == 403


def test_caller_write_surfaces(monkeypatch):
    repo = load_snapshot().repo_root
    monkeypatch.setattr(auth, "_role_tokens", {"scoped-tok": {"role": "agent", "write_surfaces": ["droplist"]}})
    assert auth.caller_write_surfaces("scoped-tok", repo) == {"droplist"}
    assert auth.caller_write_surfaces(auth.current_token(), repo) is None  # root unrestricted
    assert auth.caller_write_surfaces(None, repo) is None


def test_malformed_write_surfaces_fails_closed(monkeypatch):
    repo = load_snapshot().repo_root
    # a string typo instead of a list must DENY all writes, not silently grant them.
    monkeypatch.setattr(auth, "_role_tokens", {"typo": auth._normalize_entry({"role": "agent", "write_surfaces": "droplist"})})
    assert auth.caller_write_surfaces("typo", repo) == set()
    # absent key -> unrestricted (role-based)
    monkeypatch.setattr(auth, "_role_tokens", {"plain": auth._normalize_entry({"role": "agent"})})
    assert auth.caller_write_surfaces("plain", repo) is None
