"""PKT-007 acceptance: read-only HTTP API contract gate.

Stands up the FastAPI app from droplist.server on a random localhost port via
uvicorn (in-thread), pre-populates state with 2 DAGs in different domains, one
do-not-reopen lock, and one entity, then hits every endpoint in the contract
and asserts each:

  - returns HTTP 200
  - body decodes as JSON
  - top-level keys match the contract.returns description

Zero test deps beyond fastapi + uvicorn (already pinned as the `ui` extra in
pyproject). No pytest, no httpx. Run from the droplist service root:

    python test_server.py
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

# Stable clock so /api/now etc. are deterministic
os.environ.setdefault("DROPLIST_NOW", "2026-06-09T12:00:00Z")

# Isolated data dir for this test (must be set BEFORE importing droplist)
_TMP = tempfile.mkdtemp(prefix="pkt7_")
os.environ["DROPLIST_DATA"] = _TMP

# Make sure DROPLIST_ATLAS_SIGNALS_URL is unset so graph_engine does not
# try to POST anywhere during seeding.
os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)

import uvicorn  # noqa: E402
from droplist import auth, entities, graph_engine, state, storage  # noqa: E402
from droplist.server import app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_serving(base: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/now", timeout=0.5) as r:
                if r.getcode() < 500:
                    return True
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.1)
    sys.stderr.write(f"server never came up: {last_err}\n")
    return False


def _get_json(base: str, path: str) -> tuple[int, object | None, str | None]:
    """GET base+path. Returns (status, parsed_json_or_None, error_or_None)."""
    try:
        req = urllib.request.Request(base + path, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, None, f"http {e.code}"
    except Exception as e:  # noqa: BLE001
        return 0, None, f"{type(e).__name__}: {e}"
    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError as e:
        return status, None, f"json decode: {e}"


def _get_raw(base: str, path: str) -> tuple[int, str, str, str | None]:
    """GET base+path raw. Returns (status, content_type, text, error_or_None)."""
    try:
        req = urllib.request.Request(base + path, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return (resp.getcode(), resp.headers.get("content-type", ""),
                    resp.read().decode("utf-8"), None)
    except urllib.error.HTTPError as e:
        return e.code, "", "", f"http {e.code}"
    except Exception as e:  # noqa: BLE001
        return 0, "", "", f"{type(e).__name__}: {e}"


def _post_json(
    base: str, path: str, payload: object, token: str | None = None
) -> tuple[int, object | None, str | None]:
    """POST JSON to base+path with an optional X-Atlas-Token write header.
    Returns (status, parsed_json_or_None, error_or_None)."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(base + path, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("X-Atlas-Token", token)
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8")), None
        except Exception:  # noqa: BLE001
            return e.code, None, f"http {e.code}"
    except Exception as e:  # noqa: BLE001
        return 0, None, f"{type(e).__name__}: {e}"
    try:
        return status, json.loads(raw), None
    except json.JSONDecodeError as e:
        return status, None, f"json decode: {e}"


# ---------------------------------------------------------------------------
# Seed: 2 DAGs (different domains), 1 lock_ref, 1 entity
# ---------------------------------------------------------------------------

def _seed_state() -> str:
    # DAG #1 — animal_property domain. The "doe" token resolves to an entity,
    # so this also satisfies the "one entity" requirement organically.
    trace1 = graph_engine.run_graph(
        "The doe is limping and not eating, hiding in the corner."
    )
    # DAG #2 — money_admin domain
    graph_engine.run_graph(
        "Truck insurance renewal came in, due end of month, $612."
    )
    # one lock_ref
    state.lock_ref("SCHEMA-V1", "packet schema frozen; do not reopen")
    # one explicit entity (belt-and-suspenders alongside the doe token resolve)
    entities._ensure("PROJECT-DROPLIST", "project", "DropList")
    return trace1["dag_id"]


# ---------------------------------------------------------------------------
# Contract: endpoint -> required top-level keys
# (per server.py / command_brief.py contracts)
#
# /api/lattice/viewmodel intentionally absent: delta-kernel owns the Lattice
# surface (services/delta-kernel/src/api/server.ts:2003 + lattice-projection.ts).
# See BIBLE.md §13 OQ-18 and PACKETS/007.
# ---------------------------------------------------------------------------

def _checks(seed_dag_id: str) -> list[tuple[str, str, set[str]]]:
    return [
        ("GET /api/now", "/api/now", {"job", "after"}),
        (f"GET /api/dag/{seed_dag_id}", f"/api/dag/{seed_dag_id}",
         {"dag_id", "nodes", "status"}),
        ("GET /api/dags", "/api/dags", {"dags"}),
        ("GET /api/packets", "/api/packets", {"packets", "total"}),
        ("GET /api/state", "/api/state",
         {"recurring", "due_today", "locked_refs"}),
        ("GET /api/brief", "/api/brief",
         {"ready", "blocked", "waiting"}),
        ("GET /api/entities", "/api/entities", {"entities"}),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> int:
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level="error", access_log=False, lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()

    try:
        if not _wait_until_serving(base):
            print("PKT-007 GATE: FAIL (server failed to start)")
            return 1

        seed_dag_id = _seed_state()

        rows: list[tuple[str, str, str, bool]] = []
        for label, path, expected in _checks(seed_dag_id):
            status, body, err = _get_json(base, path)
            if status != 200:
                detail = err or f"status={status}"
                ok = False
            elif not isinstance(body, dict):
                detail = "body not a JSON object"
                ok = False
            else:
                missing = expected - set(body.keys())
                if missing:
                    detail = f"missing keys {sorted(missing)}"
                    ok = False
                else:
                    detail = f"keys {sorted(expected)} ok"
                    ok = True
            rows.append((label, str(status), detail, ok))

        # ---- UI front door (ship Task A 2026-06-25): served HTML + sample alias ----
        for label, path, marker in [
            ("GET /", "/", "DropList"),
            ("GET /chain", "/chain", "<html"),
        ]:
            st, ctype, text, err = _get_raw(base, path)
            ok = st == 200 and "text/html" in ctype and marker.lower() in text.lower()
            detail = err or (f"html+'{marker}' ok" if ok
                             else f"ctype={ctype!r} marker={marker in text}")
            rows.append((label, str(st), detail, ok))
        # /api/dag/sample must resolve to a real DAG (chain.html:323 depends on it)
        st, body, err = _get_json(base, "/api/dag/sample")
        ok = st == 200 and isinstance(body, dict) and "nodes" in body
        rows.append(("GET /api/dag/sample", str(st),
                     err or (f"keys ok ({body.get('dag_id')})" if ok else "no dag"), ok))

        # ---- Write round-trip (KEYSTONE wire, seq01 Task A) -----------------
        # The exact calls the served UI (ui/line.html EngineClient) now issues as a
        # real engine client. The engine separates capture (a secured PACKET) from
        # planning (a DAG), so the two proofs are independent:
        #   capture     -> POST /api/drop secures a packet (reflected in /api/packets)
        #   completion  -> POST .../node/{id}/complete flips a real DAG node and
        #                  writes a node_completed row to dag_events.
        # Both die in a localStorage twin before this wire; both reach the engine now.
        token = auth.current_token()

        # capture: a drop secures a packet in the engine (the drop list grows by one)
        st, body, _ = _get_json(base, "/api/packets")
        pkts_before = body.get("total") if isinstance(body, dict) else None
        w_raw = "Wire smoke: call the feed store about the 50lb rabbit pellet order."
        st, body, err = _post_json(base, "/api/drop", {"raw": w_raw}, token)
        secured = (st == 200 and isinstance(body, dict)
                   and body.get("status") == "secured")
        rows.append(("POST /api/drop (UI capture)", str(st),
                     err or (f"status={body.get('status')!r}"
                             if isinstance(body, dict) else "no body"), secured))

        st, body, _ = _get_json(base, "/api/packets")
        pkts_after = body.get("total") if isinstance(body, dict) else None
        reflected = (isinstance(pkts_before, int)
                     and pkts_after == pkts_before + 1)
        rows.append(("GET /api/packets reflects drop", "200",
                     f"total {pkts_before}->{pkts_after}", reflected))

        # completion: the UI completes the first COMPLETABLE node (status != done,
        # deps satisfied) of a DAG-backed job. Build a benign errand DAG for this --
        # the seeded 'doe' emergency routes straight to needs_human with its first
        # node already resolved, so it has nothing freshly completable.
        comp_dag_id = graph_engine.run_graph(
            "Refill the rabbit water bottles in the morning."
        )["dag_id"]
        node_id: str | None = None
        st, body, _ = _get_json(base, f"/api/dag/{comp_dag_id}/checklist")
        if st == 200 and isinstance(body, dict):
            completable = [t for t in body.get("tasks", [])
                           if t.get("status") != "done" and not t.get("blocked_by")]
            node_id = completable[0]["id"] if completable else None

        if node_id:
            st, body, err = _post_json(
                base, f"/api/dag/{comp_dag_id}/node/{node_id}/complete", {}, token)
            comp_ok = (st == 200 and isinstance(body, dict)
                       and body.get("dag_id") == comp_dag_id)
            rows.append(("POST .../node/{id}/complete", str(st),
                         err or (f"dag_status={body.get('dag_status')!r}"
                                 if isinstance(body, dict) else "no body"),
                         comp_ok))
        else:
            rows.append(("POST .../node/{id}/complete", "skip",
                         "no completable node", False))

        # the completion wrote a node_completed row to the dag_events log
        events = storage.read_all(storage.DAG_EVENTS)
        wrote_event = any(
            e.get("event") == "node_completed"
            and e.get("dag_id") == comp_dag_id
            and e.get("node_id") == node_id
            for e in events
        )
        rows.append(("dag_events node_completed", "ok" if wrote_event else "?",
                     "row present" if wrote_event else "row missing", wrote_event))

        # auth gate: the same write WITHOUT the token must be rejected (401)
        st, _, _ = _post_json(base, "/api/drop", {"raw": "no token here"}, token=None)
        rows.append(("POST /api/drop sans token", str(st), "401 expected",
                     st == 401))

        # ---- table ----
        ep_w = max(len("endpoint"), max(len(r[0]) for r in rows))
        st_w = max(len("status"), max(len(r[1]) for r in rows))
        ck_w = max(len("check"), max(len(r[2]) for r in rows))
        header = (f"  {'endpoint':<{ep_w}}  {'status':<{st_w}}  "
                  f"{'check':<{ck_w}}  result")
        sep = (f"  {'-'*ep_w}  {'-'*st_w}  {'-'*ck_w}  ------")
        print(header)
        print(sep)
        for label, status, detail, ok in rows:
            verdict = "PASS" if ok else "FAIL"
            print(f"  {label:<{ep_w}}  {status:<{st_w}}  "
                  f"{detail:<{ck_w}}  {verdict}")

        all_pass = all(r[3] for r in rows)
        print()
        print("PKT-007 GATE: PASS" if all_pass else "PKT-007 GATE: FAIL")
        return 0 if all_pass else 1
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
