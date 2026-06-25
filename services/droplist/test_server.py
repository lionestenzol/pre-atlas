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
from droplist import entities, graph_engine, state  # noqa: E402
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
