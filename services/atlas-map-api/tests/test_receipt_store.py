"""Tests for the durable Receipt store (LangGraph Skill Lattice plan, Seq 1).

Covers the store module in isolation (append/read against a tmp_path store)
and the /seam/call + /seam/receipts endpoints' actual wiring.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_map_api import receipt_store


def test_append_then_read_by_run_id(tmp_path):
    receipt_store.append(tmp_path, "run-a", {"tool": "sigil", "status": "ok", "sha256": "abc"})
    receipt_store.append(tmp_path, "run-a", {"tool": "binre", "status": "ok", "sha256": "def"})
    receipt_store.append(tmp_path, "run-b", {"tool": "sigil", "status": "error", "sha256": None})

    rows = receipt_store.read(tmp_path, "run-a")
    assert len(rows) == 2
    assert [r["tool"] for r in rows] == ["sigil", "binre"]  # insertion order preserved
    assert all(r["run_id"] == "run-a" for r in rows)


def test_read_with_no_run_id_returns_everything(tmp_path):
    receipt_store.append(tmp_path, "run-a", {"tool": "sigil", "status": "ok"})
    receipt_store.append(tmp_path, "run-b", {"tool": "binre", "status": "ok"})
    assert len(receipt_store.read(tmp_path)) == 2


def test_read_unknown_run_id_is_empty_not_an_error(tmp_path):
    receipt_store.append(tmp_path, "run-a", {"tool": "sigil", "status": "ok"})
    assert receipt_store.read(tmp_path, "no-such-run") == []


def test_read_before_any_append_is_empty(tmp_path):
    assert receipt_store.read(tmp_path, "never-called") == []


def test_sha256_is_persisted_verbatim_not_regenerated(tmp_path):
    receipt_store.append(tmp_path, "run-a", {"tool": "sigil", "status": "ok", "sha256": "stable-sha"})
    receipt_store.append(tmp_path, "run-a", {"tool": "sigil", "status": "ok", "sha256": "stable-sha"})
    rows = receipt_store.read(tmp_path, "run-a")
    assert [r["sha256"] for r in rows] == ["stable-sha", "stable-sha"]


def test_corrupt_line_does_not_block_reading_the_rest(tmp_path):
    path = tmp_path / "services" / "atlas-map-api" / "var" / "receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"run_id": "run-a", "tool": "sigil"}\nnot json\n', encoding="utf-8")
    rows = receipt_store.read(tmp_path, "run-a")
    assert len(rows) == 1 and rows[0]["tool"] == "sigil"


# ---- endpoint wiring: /seam/call persists, /seam/receipts reads it back -------
def _client(monkeypatch, tmp_path):
    from atlas_map_api import gateway as gateway_mod
    from atlas_map_api import server
    from atlas_map_api.loader import MapSnapshot

    snap = MapSnapshot(
        repo_root=tmp_path, generated_at="test", subsystems={}, service_edges=(), retired=frozenset(),
    )
    monkeypatch.setattr(server, "_ensure_loaded", lambda: (snap, None))

    async def fake_call_capability(_snap, surface, capability, args, token, role_name=None):
        return {"ok": True, "surface": surface, "kind": "cli", "status": 0,
                "data": {"stdout": '{"sha256": "abc123"}', "stderr": ""}, "error": None, "meta": {}}

    monkeypatch.setattr(gateway_mod, "call_capability", fake_call_capability)
    return TestClient(server.app)


def test_seam_call_endpoint_persists_and_echoes_run_id(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    r1 = client.post("/seam/call", json={"surface": "sigil", "capability": "info"})
    assert r1.status_code == 200
    body1 = r1.json()
    run_id = body1["run_id"]
    assert run_id  # auto-generated when the caller omits it
    assert body1["sha256"] == "abc123"

    r2 = client.post("/seam/call", json={"surface": "sigil", "capability": "info", "run_id": run_id})
    assert r2.status_code == 200
    assert r2.json()["run_id"] == run_id

    got = client.get("/seam/receipts", params={"run_id": run_id})
    assert got.status_code == 200
    receipts = got.json()["receipts"]
    assert len(receipts) == 2  # both POSTs landed under the shared run_id
    assert {r["sha256"] for r in receipts} == {"abc123"}  # stable across the two calls


def test_seam_receipts_endpoint_unknown_run_id_returns_empty(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    got = client.get("/seam/receipts", params={"run_id": "never-called"})
    assert got.status_code == 200
    assert got.json() == {"run_id": "never-called", "receipts": []}
