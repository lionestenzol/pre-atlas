"""Intake chainer acceptance: the POST /api/drop bouncer + chainer.

Mirrors test_server.py's zero-dep style (in-thread uvicorn, isolated data dir,
urllib only). Covers the two gates and the happy path:

  - fresh input            -> 200 {status: secured}, packet stored, delta_hash set
  - same input again       -> 200 {status: dropped, reason: duplicate ...}, NOT stored
  - whitespace/short input -> 200 {status: dropped, reason: noise ...}, NOT stored
  - non-JSON body          -> 4xx
  - direct chain_intake()  -> unit-level check of the same three verdicts

Run from the droplist service root:

    python test_intake.py
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

os.environ.setdefault("DROPLIST_NOW", "2026-06-21T12:00:00Z")

_TMP = tempfile.mkdtemp(prefix="intake_")
os.environ["DROPLIST_DATA"] = _TMP
# Keep the heuristic backend + no atlas emission so the test is offline + fast.
os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)
os.environ.setdefault("DROPLIST_LLM", "heuristic")

import uvicorn  # noqa: E402
from droplist import intake, storage  # noqa: E402
from droplist.server import app  # noqa: E402


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


def _post_json(base: str, path: str, body: object) -> tuple[int, object | None, str | None]:
    """POST JSON body to base+path. Returns (status, parsed_json_or_None, error)."""
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    try:
        req = urllib.request.Request(
            base + path, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
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


def _packet_count() -> int:
    return len(storage.read_all(storage.PACKETS))


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

    rows: list[tuple[str, str, bool]] = []

    def check(label: str, detail: str, ok: bool) -> None:
        rows.append((label, detail, ok))

    try:
        if not _wait_until_serving(base):
            print("INTAKE GATE: FAIL (server failed to start)")
            return 1

        fresh = "Truck insurance renewal due end of month, $612."

        # 1) fresh drop -> secured + stored
        before = _packet_count()
        st, body, err = _post_json(base, "/api/drop", {"rawInput": fresh})
        ok = (
            st == 200 and isinstance(body, dict)
            and body.get("status") == "secured"
            and bool(body.get("delta_hash"))
            and bool(body.get("drop_id"))
            and _packet_count() == before + 1
        )
        check("POST fresh -> secured", err or f"status={body.get('status') if isinstance(body, dict) else body}", ok)
        secured_hash = body.get("delta_hash") if isinstance(body, dict) else None

        # 2) same drop again -> dropped (duplicate), NOT stored
        before = _packet_count()
        st, body, err = _post_json(base, "/api/drop", {"rawInput": fresh})
        ok = (
            st == 200 and isinstance(body, dict)
            and body.get("status") == "dropped"
            and "duplicate" in str(body.get("reason", ""))
            and body.get("delta_hash") == secured_hash
            and _packet_count() == before  # nothing new stored
        )
        check("POST duplicate -> dropped", err or f"reason={body.get('reason') if isinstance(body, dict) else body}", ok)

        # 3) whitespace-only -> dropped (noise), NOT stored
        before = _packet_count()
        st, body, err = _post_json(base, "/api/drop", {"raw": "   \t  "})
        ok = (
            st == 200 and isinstance(body, dict)
            and body.get("status") == "dropped"
            and "noise" in str(body.get("reason", ""))
            and _packet_count() == before
        )
        check("POST noise -> dropped", err or f"reason={body.get('reason') if isinstance(body, dict) else body}", ok)

        # 4) malformed (non-JSON) body -> 4xx
        st, body, err = _post_json(base, "/api/drop", b"not json at all")
        ok = 400 <= st < 500
        check("POST bad body -> 4xx", f"status={st}", ok)

        # 5) direct unit check of chain_intake (no HTTP)
        u_secured = intake.chain_intake("A brand new unique idea about goat bedding rotation.")
        u_dup = intake.chain_intake("A brand new unique idea about goat bedding rotation.")
        u_noise = intake.chain_intake("  ")
        ok = (
            u_secured.get("status") == "secured"
            and u_dup.get("status") == "dropped" and "duplicate" in u_dup.get("reason", "")
            and u_noise.get("status") == "dropped" and "noise" in u_noise.get("reason", "")
        )
        check("unit chain_intake verdicts", f"{u_secured.get('status')}/{u_dup.get('status')}/{u_noise.get('status')}", ok)

        # ---- table ----
        lbl_w = max(len("check"), max(len(r[0]) for r in rows))
        dt_w = max(len("detail"), max(len(r[1]) for r in rows))
        print(f"  {'check':<{lbl_w}}  {'detail':<{dt_w}}  result")
        print(f"  {'-'*lbl_w}  {'-'*dt_w}  ------")
        for label, detail, ok in rows:
            print(f"  {label:<{lbl_w}}  {detail:<{dt_w}}  {'PASS' if ok else 'FAIL'}")

        all_pass = all(r[2] for r in rows)
        print()
        print("INTAKE GATE: PASS" if all_pass else "INTAKE GATE: FAIL")
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
