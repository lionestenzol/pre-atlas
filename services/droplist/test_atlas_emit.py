"""PKT-006 acceptance: live Atlas signal emission from graph_engine.

Stands up a stdlib HTTPServer on a random localhost port, sets
DROPLIST_ATLAS_SIGNALS_URL to it, runs one drop through graph_engine,
and asserts:

  1. Exactly one POST was received.
  2. Content-Type was application/json.
  3. Body parses as JSON and structurally matches Signal.v1.
  4. dag_events.jsonl contains exactly one atlas_signal_emit record with ok=true.

  Negative case: with the env var unset, no POST and no emit event.

Zero external deps. Run from project root:

    python test_atlas_emit.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Stable clock for reproducible signals
os.environ.setdefault("DROPLIST_NOW", "2026-06-08T12:00:00Z")

# Isolated data dir for this test (must be set BEFORE importing droplist)
_TMP = tempfile.mkdtemp(prefix="pkt6_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import graph_engine, storage  # noqa: E402

# Reuse structural checker from PKT-005 test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_atlas_signal import structural_check  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal stdlib HTTP server that captures POSTs
# ---------------------------------------------------------------------------

class _CaptureHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self.received.append({
            "path": self.path,
            "content_type": self.headers.get("Content-Type", ""),
            "body_raw": body,
        })
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "signal_id": "test-sig-123"}')

    def log_message(self, *args, **kwargs):  # silence stderr noise
        pass


def _start_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/api/signals/ingest"


# ---------------------------------------------------------------------------
# Test runs
# ---------------------------------------------------------------------------

def case_positive_emits_signal() -> list[str]:
    """With env var set, exactly one Signal.v1 POST happens."""
    errs: list[str] = []
    _CaptureHandler.received.clear()
    server, url = _start_server()
    try:
        os.environ["DROPLIST_ATLAS_SIGNALS_URL"] = url

        # Snapshot DAG_EVENTS line count before
        events_before = len(storage.read_all(storage.DAG_EVENTS))

        # Run a drop that produces a settled DAG (warning -> approval_required)
        graph_engine.run_graph("The doe is limping and not eating, hiding in the corner.")

        # 1. Exactly one POST received
        recvd = list(_CaptureHandler.received)
        if len(recvd) != 1:
            errs.append(f"expected exactly 1 POST, got {len(recvd)}")
            return errs

        post = recvd[0]
        # 2. Content-Type
        if "application/json" not in post["content_type"]:
            errs.append(f"content-type missing application/json: {post['content_type']!r}")

        # 3. Body parses + structural Signal.v1
        try:
            sig = json.loads(post["body_raw"])
        except json.JSONDecodeError as e:
            errs.append(f"body not valid JSON: {e}")
            return errs

        struct_errs = structural_check(sig)
        if struct_errs:
            errs.extend(f"structural: {e}" for e in struct_errs)

        # 4. dag_events.jsonl has one atlas_signal_emit record with ok=true
        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        emit_events = [e for e in new_events if e.get("event") == "atlas_signal_emit"]
        if len(emit_events) != 1:
            errs.append(f"expected 1 atlas_signal_emit event, got {len(emit_events)}")
        elif not emit_events[0].get("ok"):
            errs.append(f"emit event ok=False: {emit_events[0]}")
        elif not emit_events[0].get("signal_id"):
            errs.append("emit event missing signal_id")
    finally:
        os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)
        server.shutdown()
        server.server_close()
    return errs


def case_negative_no_env_no_emit() -> list[str]:
    """With env var unset, NO POST and NO emit event."""
    errs: list[str] = []
    _CaptureHandler.received.clear()
    server, url = _start_server()
    try:
        os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)

        events_before = len(storage.read_all(storage.DAG_EVENTS))
        graph_engine.run_graph("Truck insurance renewal came in, due end of month, $612.")

        if _CaptureHandler.received:
            errs.append(f"expected 0 POSTs with env unset, got {len(_CaptureHandler.received)}")

        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        emit_events = [e for e in new_events if e.get("event") == "atlas_signal_emit"]
        if emit_events:
            errs.append(f"expected 0 atlas_signal_emit events with env unset, got {len(emit_events)}")
    finally:
        server.shutdown()
        server.server_close()
    return errs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> int:
    print("PKT-006 LIVE ATLAS EMISSION ACCEPTANCE\n" + "-" * 64)
    cases = [
        ("positive: env set -> one Signal.v1 POST + audit event", case_positive_emits_signal),
        ("negative: env unset -> no POST, no audit event", case_negative_no_env_no_emit),
    ]
    all_pass = True
    for label, fn in cases:
        errs = fn()
        ok = not errs
        print(f"  [{'OK' if ok else 'XX'}] {label}")
        for e in errs:
            print(f"      err: {e}")
        if not ok:
            all_pass = False
    print("-" * 64)
    print("PKT-006 GATE: PASS" if all_pass else "PKT-006 GATE: FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
