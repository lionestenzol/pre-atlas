"""DropList remediation Stop 3 acceptance: production-side Signal.v1 validation.

Covers:
  1. validate_signal returns [] for a valid Signal.v1 dict (produced by dag_to_signal).
  2. validate_signal returns non-empty errors for a malformed Signal.
  3. emit_signal in DROPLIST_STRICT_EMIT mode returns ok=False with validation_errors
     and does NOT POST for an invalid signal.
  4. emit_signal in default (fail-soft) mode logs a `signal_validation_warning` event
     to dag_events.jsonl AND still POSTs for an invalid signal.
  5. emit_signal does not interfere with normal POST flow for valid signals.

Stands up a stdlib HTTPServer on a random localhost port to capture POSTs.
Zero external deps. Run from project root:

    python test_atlas_validate.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Stable clock for reproducible emitted_at
os.environ.setdefault("DROPLIST_NOW", "2026-06-08T12:00:00Z")

# Isolated data dir for this test (must be set BEFORE importing droplist)
_TMP = tempfile.mkdtemp(prefix="pkt_stop3_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import atlas_signal, storage  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_atlas_signal import fixture_animal_needs_human  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal stdlib HTTP server that captures POSTs
# ---------------------------------------------------------------------------

class _CaptureHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self.received.append({"path": self.path, "body_raw": body})
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "signal_id": "test-sig-stop3"}')

    def log_message(self, *args, **kwargs):  # silence stderr noise
        pass


def _start_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/api/signals/ingest"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_signal() -> dict:
    """Produce a fully-valid Signal.v1 dict via the canonical mapper."""
    return atlas_signal.dag_to_signal(fixture_animal_needs_human())


def _make_invalid_signal() -> dict:
    """Mutate a valid signal so it fails validation in multiple ways.

    - signal_type is not in the closed enum
    - priority is not in the closed enum
    - payload.data is missing required sub-fields
    """
    sig = _make_valid_signal()
    sig["signal_type"] = "not_a_real_type"
    sig["priority"] = "screaming"
    # Drop several required payload.data sub-fields
    if "data" in sig["payload"]:
        for k in ("dag_id", "domain", "links"):
            sig["payload"]["data"].pop(k, None)
    return sig


def _clear_strict_env() -> None:
    os.environ.pop("DROPLIST_STRICT_EMIT", None)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def case_validate_signal_passes_for_valid() -> list[str]:
    """validate_signal returns [] for a Signal produced by dag_to_signal."""
    errs: list[str] = []
    sig = _make_valid_signal()
    result = atlas_signal.validate_signal(sig)
    if result:
        errs.append(f"expected [], got {result}")
    return errs


def case_validate_signal_catches_invalid() -> list[str]:
    """validate_signal returns non-empty errors for a malformed Signal."""
    errs: list[str] = []
    bad = _make_invalid_signal()
    result = atlas_signal.validate_signal(bad)
    if not result:
        errs.append("expected validation errors, got []")
    # Either jsonschema (single concise message) or structural (multiple) is fine.
    # Sanity check that something was caught.
    return errs


def case_validate_signal_rejects_non_dict() -> list[str]:
    """validate_signal returns an error message for non-dict input."""
    errs: list[str] = []
    for bad_input in (None, "not a dict", 42, [1, 2, 3]):
        result = atlas_signal.validate_signal(bad_input)  # type: ignore[arg-type]
        if not result:
            errs.append(f"expected error for {bad_input!r}, got []")
    return errs


def case_strict_mode_returns_error_no_post() -> list[str]:
    """In strict mode, an invalid signal returns ok=False AND does not POST."""
    errs: list[str] = []
    _CaptureHandler.received.clear()
    server, url = _start_server()
    try:
        os.environ["DROPLIST_STRICT_EMIT"] = "1"
        bad = _make_invalid_signal()
        events_before = len(storage.read_all(storage.DAG_EVENTS))

        resp = atlas_signal.emit_signal(bad, url)

        if resp.get("ok") is not False:
            errs.append(f"expected ok=False, got {resp}")
        if resp.get("error") != "validation_failed":
            errs.append(f"expected error='validation_failed', got {resp.get('error')!r}")
        if not isinstance(resp.get("validation_errors"), list) or not resp["validation_errors"]:
            errs.append("expected validation_errors list with >=1 entry")

        if _CaptureHandler.received:
            errs.append(f"expected 0 POSTs in strict mode, got {len(_CaptureHandler.received)}")

        # Audit event recorded
        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        warns = [e for e in new_events if e.get("event") == "signal_validation_warning"]
        if len(warns) != 1:
            errs.append(f"expected 1 signal_validation_warning, got {len(warns)}")
        elif warns[0].get("strict_mode") is not True:
            errs.append(f"expected strict_mode=True in event, got {warns[0].get('strict_mode')}")
        elif warns[0].get("posted") is not False:
            errs.append(f"expected posted=False in event, got {warns[0].get('posted')}")
    finally:
        _clear_strict_env()
        server.shutdown()
        server.server_close()
    return errs


def case_fail_soft_mode_logs_and_posts() -> list[str]:
    """In default (fail-soft) mode, an invalid signal logs warning AND still POSTs."""
    errs: list[str] = []
    _CaptureHandler.received.clear()
    server, url = _start_server()
    try:
        _clear_strict_env()  # ensure off
        bad = _make_invalid_signal()
        events_before = len(storage.read_all(storage.DAG_EVENTS))

        resp = atlas_signal.emit_signal(bad, url)

        # POST should have happened — the test server returns 202 + ok=true body
        if not resp.get("ok"):
            errs.append(f"expected ok=True in fail-soft mode, got {resp}")

        if len(_CaptureHandler.received) != 1:
            errs.append(f"expected 1 POST in fail-soft mode, got {len(_CaptureHandler.received)}")

        # Audit event recorded with posted=True and strict_mode=False
        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        warns = [e for e in new_events if e.get("event") == "signal_validation_warning"]
        if len(warns) != 1:
            errs.append(f"expected 1 signal_validation_warning, got {len(warns)}")
        else:
            w = warns[0]
            if w.get("strict_mode") is not False:
                errs.append(f"expected strict_mode=False, got {w.get('strict_mode')}")
            if w.get("posted") is not True:
                errs.append(f"expected posted=True, got {w.get('posted')}")
            if not isinstance(w.get("errors"), list) or not w["errors"]:
                errs.append("expected non-empty errors list in event")
    finally:
        server.shutdown()
        server.server_close()
    return errs


def case_valid_signal_passes_through_emit() -> list[str]:
    """A valid Signal emits cleanly with no warning event in either mode."""
    errs: list[str] = []
    _CaptureHandler.received.clear()
    server, url = _start_server()
    try:
        _clear_strict_env()
        good = _make_valid_signal()
        events_before = len(storage.read_all(storage.DAG_EVENTS))

        resp = atlas_signal.emit_signal(good, url)

        if not resp.get("ok"):
            errs.append(f"expected ok=True for valid signal, got {resp}")
        if len(_CaptureHandler.received) != 1:
            errs.append(f"expected 1 POST for valid signal, got {len(_CaptureHandler.received)}")

        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        warns = [e for e in new_events if e.get("event") == "signal_validation_warning"]
        if warns:
            errs.append(f"expected 0 warning events for valid signal, got {len(warns)}")

        # Also confirm strict mode still POSTs a valid signal.
        _CaptureHandler.received.clear()
        os.environ["DROPLIST_STRICT_EMIT"] = "1"
        events_before = len(storage.read_all(storage.DAG_EVENTS))
        resp2 = atlas_signal.emit_signal(good, url)
        if not resp2.get("ok"):
            errs.append(f"expected ok=True for valid signal in strict mode, got {resp2}")
        if len(_CaptureHandler.received) != 1:
            errs.append(
                f"expected 1 POST for valid signal in strict mode, got {len(_CaptureHandler.received)}"
            )
        events_after = storage.read_all(storage.DAG_EVENTS)
        new_events = events_after[events_before:]
        warns2 = [e for e in new_events if e.get("event") == "signal_validation_warning"]
        if warns2:
            errs.append(f"expected 0 warning events for valid+strict, got {len(warns2)}")
    finally:
        _clear_strict_env()
        server.shutdown()
        server.server_close()
    return errs


# ---------------------------------------------------------------------------
# pytest-style entry points (also support direct python invocation)
# ---------------------------------------------------------------------------

def test_validate_signal_passes_for_valid():
    assert case_validate_signal_passes_for_valid() == []


def test_validate_signal_catches_invalid():
    assert case_validate_signal_catches_invalid() == []


def test_validate_signal_rejects_non_dict():
    assert case_validate_signal_rejects_non_dict() == []


def test_strict_mode_returns_error_no_post():
    assert case_strict_mode_returns_error_no_post() == []


def test_fail_soft_mode_logs_and_posts():
    assert case_fail_soft_mode_logs_and_posts() == []


def test_valid_signal_passes_through_emit():
    assert case_valid_signal_passes_through_emit() == []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> int:
    print("REMEDIATION STOP-3 PROD VALIDATION ACCEPTANCE\n" + "-" * 64)
    cases = [
        ("validate_signal: valid -> []", case_validate_signal_passes_for_valid),
        ("validate_signal: invalid -> errors", case_validate_signal_catches_invalid),
        ("validate_signal: non-dict -> error", case_validate_signal_rejects_non_dict),
        ("emit + strict: invalid -> error, no POST", case_strict_mode_returns_error_no_post),
        ("emit + fail-soft: invalid -> warn + POST", case_fail_soft_mode_logs_and_posts),
        ("emit: valid passes through cleanly", case_valid_signal_passes_through_emit),
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
    print("STOP-3 GATE: PASS" if all_pass else "STOP-3 GATE: FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
