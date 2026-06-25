"""DropList Stop 4 acceptance: PKT-006 retry buffer.

Covers the retry_queue lifecycle:

  (a) test_first_attempt_success_no_queue_write
      Successful POST -> queue stays empty, no signal_retry_* event.

  (b) test_failure_enqueues_with_attempts_zero
      Unreachable URL -> emit_signal returns ok=False AND lands one entry on
      the queue with attempts=0 and a future next_attempt_at.

  (c) test_retry_on_next_settle_drains_and_reposts
      Queue an entry against a failing URL, then point the queue entry at a
      succeeding HTTPServer + monkeypatch BACKOFF to 0s. Drain + emit + mark
      attempted; queue becomes empty and signal_retry_success is logged.

  (d) test_max_attempts_exhausted_drops_and_logs
      Five failed mark_attempted calls (0 -> 1 -> 2 -> 3 -> 4 -> 5). At the
      fifth, the entry is dropped and signal_retry_exhausted is logged.

  (e) test_ttl_pruned_after_seven_days
      Enqueue at T0, advance DROPLIST_NOW to T0+8d, call prune_expired().
      Returns 1, signal_retry_pruned event with reason=ttl_expired logged.

  (f) test_dedup_by_signal_id
      enqueue() twice with same signal_id -> only one entry, second call
      returns False.

  (g) test_strict_emit_validation_failure_does_not_enqueue
      DROPLIST_STRICT_EMIT=1 + invalid signal -> validation_failed error
      AND queue stays empty (Stop-3 contract preserved).

  (h) test_4xx_response_does_not_enqueue
      HTTPServer returns 400 -> ok=False but queue stays empty (4xx is a
      client-side bug, not a transient failure).

Stands up a stdlib HTTPServer on a random localhost port to capture POSTs.
Zero external deps. Run from project root:

    python test_atlas_retry.py
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
_TMP = tempfile.mkdtemp(prefix="pkt6_retry_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import atlas_signal, clock, retry_queue, storage  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_atlas_signal import fixture_animal_needs_human  # noqa: E402


# ---------------------------------------------------------------------------
# HTTP servers (capturing + failing)
# ---------------------------------------------------------------------------


class _CaptureHandler(BaseHTTPRequestHandler):
    """202 + ok=true on every POST. Records bodies for assertions."""
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self.received.append({"path": self.path, "body_raw": body})
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "signal_id": "test-sig-retry"}')

    def log_message(self, *args, **kwargs):  # silence stderr
        pass


class _400Handler(BaseHTTPRequestHandler):
    """Returns 400 to simulate a client-side bug (non-retryable)."""
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        self.received.append({"path": self.path})
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": false, "error": "bad request"}')

    def log_message(self, *args, **kwargs):
        pass


class _503Handler(BaseHTTPRequestHandler):
    """Returns 503 to simulate a transient server error (retryable)."""
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.rfile.read(length)
        self.received.append({"path": self.path})
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": false, "error": "service unavailable"}')

    def log_message(self, *args, **kwargs):
        pass


def _start_server(handler_cls) -> tuple[HTTPServer, str]:
    handler_cls.received.clear()
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/api/signals/ingest"


# Port 1 is reserved and refuses TCP connections — perfect for forcing OSError.
_UNREACHABLE_URL = "http://127.0.0.1:1/api/signals/ingest"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Wipe queue file + dag_events between cases for clean assertions.

    Also pops env vars that some cases override so they don't bleed across.
    """
    qpath = os.path.join(storage.DATA_DIR, retry_queue.QUEUE_FILE)
    if os.path.exists(qpath):
        os.unlink(qpath)
    epath = os.path.join(storage.DATA_DIR, storage.DAG_EVENTS)
    if os.path.exists(epath):
        os.unlink(epath)
    os.environ.pop("DROPLIST_STRICT_EMIT", None)
    # Restore the module-load clock baseline; specific cases override and restore.
    os.environ["DROPLIST_NOW"] = "2026-06-08T12:00:00Z"


def _make_signal() -> dict:
    """Produce a valid Signal.v1 dict via the canonical mapper."""
    return atlas_signal.dag_to_signal(fixture_animal_needs_human())


def _make_invalid_signal() -> dict:
    sig = _make_signal()
    sig["signal_type"] = "not_a_real_type"
    sig["priority"] = "screaming"
    return sig


def _read_queue() -> list[dict]:
    return retry_queue._read_entries()  # ok in tests — same package


def _read_events() -> list[dict]:
    return storage.read_all(storage.DAG_EVENTS)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_first_attempt_success_no_queue_write() -> list[str]:
    """Successful POST never touches the queue or logs retry events."""
    errs: list[str] = []
    _reset_state()
    server, url = _start_server(_CaptureHandler)
    try:
        sig = _make_signal()
        resp = atlas_signal.emit_signal(sig, url)
        if not resp.get("ok"):
            errs.append(f"expected ok=True, got {resp}")
        if len(_CaptureHandler.received) != 1:
            errs.append(f"expected 1 POST, got {len(_CaptureHandler.received)}")
        if _read_queue():
            errs.append(f"expected empty queue, got {_read_queue()}")
        retry_events = [e for e in _read_events()
                        if isinstance(e.get("event"), str)
                        and e["event"].startswith("signal_retry_")]
        if retry_events:
            errs.append(f"expected no signal_retry_* events, got {retry_events}")
    finally:
        server.shutdown()
        server.server_close()
    return errs


def case_failure_enqueues_with_attempts_zero() -> list[str]:
    """Unreachable URL enqueues one entry with attempts=0."""
    errs: list[str] = []
    _reset_state()
    sig = _make_signal()
    resp = atlas_signal.emit_signal(sig, _UNREACHABLE_URL)
    if resp.get("ok") is not False:
        errs.append(f"expected ok=False on unreachable URL, got {resp}")

    queue = _read_queue()
    if len(queue) != 1:
        errs.append(f"expected exactly 1 queued entry, got {len(queue)}: {queue}")
        return errs

    entry = queue[0]
    if entry.get("attempts") != 0:
        errs.append(f"expected attempts=0, got {entry.get('attempts')}")
    if entry.get("signal_id") != sig.get("id"):
        errs.append(f"signal_id mismatch: queued={entry.get('signal_id')!r} "
                    f"vs signal={sig.get('id')!r}")
    if not entry.get("first_attempt_at"):
        errs.append("expected first_attempt_at to be set")
    if not entry.get("next_attempt_at"):
        errs.append("expected next_attempt_at to be set")
    # next_attempt_at must be after first_attempt_at (backoff window applied)
    first = clock.parse(entry.get("first_attempt_at"))
    nxt = clock.parse(entry.get("next_attempt_at"))
    if first is None or nxt is None or nxt <= first:
        errs.append(f"next_attempt_at ({nxt}) must follow first_attempt_at ({first})")
    if not isinstance(entry.get("last_error"), str) or not entry.get("last_error"):
        errs.append(f"expected non-empty last_error, got {entry.get('last_error')!r}")
    if entry.get("url") != _UNREACHABLE_URL:
        errs.append(f"url mismatch: {entry.get('url')!r}")
    # Defense-in-depth: the full Signal.v1 payload must be preserved so the
    # retry pump has the original body to re-POST. Without this, a regression
    # that stored only signal_id + url would silently break drain.
    stored_sig = entry.get("signal")
    if not isinstance(stored_sig, dict):
        errs.append(f"expected entry['signal'] to be a preserved dict, got {type(stored_sig).__name__}")
    else:
        if stored_sig.get("id") != sig.get("id"):
            errs.append(f"signal payload corrupted: id={stored_sig.get('id')!r} vs {sig.get('id')!r}")
        if stored_sig.get("schema_version") != "1.0":
            errs.append(f"signal payload corrupted: schema_version={stored_sig.get('schema_version')!r}")
        if not isinstance(stored_sig.get("payload"), dict):
            errs.append("signal payload corrupted: payload dict missing")
    return errs


def case_retry_on_next_settle_drains_and_reposts() -> list[str]:
    """Drain a queued entry against a succeeding server -> entry retires + success event."""
    errs: list[str] = []
    _reset_state()

    # Step 1: enqueue against unreachable URL
    sig = _make_signal()
    atlas_signal.emit_signal(sig, _UNREACHABLE_URL)
    if len(_read_queue()) != 1:
        errs.append("setup failed: expected 1 queued entry after initial failure")
        return errs

    # Step 2: monkeypatch BACKOFF_SECONDS to 0 so the entry is immediately due,
    # then redirect to a succeeding server.
    original_backoff = retry_queue.BACKOFF_SECONDS[:]
    retry_queue.BACKOFF_SECONDS[:] = [0, 0, 0, 0, 0]

    server, good_url = _start_server(_CaptureHandler)
    try:
        # Patch the queued entry's URL to the succeeding server (real-world
        # callers would point at the same DROPLIST_ATLAS_SIGNALS_URL, but the
        # entry-URL is what drain uses).
        entries = _read_queue()
        entries[0]["url"] = good_url
        # Force entry to be due now by zeroing next_attempt_at to a past time.
        entries[0]["next_attempt_at"] = "2026-06-08T11:00:00Z"
        retry_queue._atomic_rewrite(entries)

        # Step 3: drain and replay
        due = retry_queue.drain()
        if len(due) != 1:
            errs.append(f"expected 1 due entry, got {len(due)}")
            return errs

        for entry in due:
            resp = atlas_signal.emit_signal(entry["signal"], entry["url"])
            retry_queue.mark_attempted(entry, success=bool(resp.get("ok")))

        # Step 4: queue should now be empty
        if _read_queue():
            errs.append(f"expected empty queue after success, got {_read_queue()}")

        # Step 5: success event logged
        success_events = [e for e in _read_events()
                          if e.get("event") == "signal_retry_success"]
        if len(success_events) != 1:
            errs.append(f"expected 1 signal_retry_success event, got {len(success_events)}")
        elif success_events[0].get("signal_id") != sig.get("id"):
            errs.append(f"success event signal_id mismatch: "
                        f"{success_events[0].get('signal_id')!r} vs {sig.get('id')!r}")

        # And the succeeding server actually received the POST
        if len(_CaptureHandler.received) != 1:
            errs.append(f"expected 1 retry POST, got {len(_CaptureHandler.received)}")
    finally:
        retry_queue.BACKOFF_SECONDS[:] = original_backoff
        server.shutdown()
        server.server_close()
    return errs


def case_max_attempts_exhausted_drops_and_logs() -> list[str]:
    """Five failed mark_attempted calls retire the entry and log exhausted."""
    errs: list[str] = []
    _reset_state()

    sig = _make_signal()
    atlas_signal.emit_signal(sig, _UNREACHABLE_URL)
    if len(_read_queue()) != 1:
        errs.append("setup failed: expected 1 queued entry")
        return errs

    # Drive 5 failed attempts. After each, fetch the entry fresh from the queue
    # so we see the on-disk attempts counter increment.
    for i in range(retry_queue.MAX_ATTEMPTS):
        queue = _read_queue()
        if i < retry_queue.MAX_ATTEMPTS - 1:
            if len(queue) != 1:
                errs.append(f"iter {i}: expected 1 queued entry, got {len(queue)}")
                return errs
            entry = queue[0]
            expected_attempts = i
            if entry.get("attempts") != expected_attempts:
                errs.append(f"iter {i}: expected attempts={expected_attempts}, "
                            f"got {entry.get('attempts')}")
            retry_queue.mark_attempted(entry, success=False)
        else:
            # Last iteration — entry should still be present with attempts=4
            # before the call; after the call it should be retired.
            entry = queue[0]
            if entry.get("attempts") != retry_queue.MAX_ATTEMPTS - 1:
                errs.append(f"final iter: expected attempts="
                            f"{retry_queue.MAX_ATTEMPTS - 1} before exhaust, "
                            f"got {entry.get('attempts')}")
            retry_queue.mark_attempted(entry, success=False)

    # Queue should be empty now
    final_queue = _read_queue()
    if final_queue:
        errs.append(f"expected empty queue after exhaustion, got {final_queue}")

    # Exhausted event logged exactly once with the right signal_id
    exh_events = [e for e in _read_events()
                  if e.get("event") == "signal_retry_exhausted"]
    if len(exh_events) != 1:
        errs.append(f"expected 1 signal_retry_exhausted event, got {len(exh_events)}")
    elif exh_events[0].get("signal_id") != sig.get("id"):
        errs.append(f"exhausted event signal_id mismatch: "
                    f"{exh_events[0].get('signal_id')!r}")
    elif exh_events[0].get("attempts") != retry_queue.MAX_ATTEMPTS:
        errs.append(f"exhausted event attempts={exh_events[0].get('attempts')}, "
                    f"expected {retry_queue.MAX_ATTEMPTS}")
    return errs


def case_ttl_pruned_after_seven_days() -> list[str]:
    """Advance clock past TTL window -> entry pruned with reason=ttl_expired."""
    errs: list[str] = []
    _reset_state()
    original_now = os.environ.get("DROPLIST_NOW")
    try:
        # Enqueue at T0
        sig = _make_signal()
        atlas_signal.emit_signal(sig, _UNREACHABLE_URL)
        if len(_read_queue()) != 1:
            errs.append("setup failed: expected 1 queued entry at T0")
            return errs

        # Advance to T0 + 8 days
        os.environ["DROPLIST_NOW"] = "2026-06-16T12:00:00Z"

        removed = retry_queue.prune_expired()
        if removed != 1:
            errs.append(f"expected prune_expired() to return 1, got {removed}")
        if _read_queue():
            errs.append(f"expected empty queue after prune, got {_read_queue()}")

        pruned_events = [e for e in _read_events()
                         if e.get("event") == "signal_retry_pruned"]
        if len(pruned_events) != 1:
            errs.append(f"expected 1 signal_retry_pruned event, "
                        f"got {len(pruned_events)}")
        elif pruned_events[0].get("reason") != "ttl_expired":
            errs.append(f"expected reason=ttl_expired, "
                        f"got {pruned_events[0].get('reason')!r}")
        elif pruned_events[0].get("signal_id") != sig.get("id"):
            errs.append(f"pruned event signal_id mismatch: "
                        f"{pruned_events[0].get('signal_id')!r}")
    finally:
        if original_now is not None:
            os.environ["DROPLIST_NOW"] = original_now
        else:
            os.environ.pop("DROPLIST_NOW", None)
    return errs


def case_dedup_by_signal_id() -> list[str]:
    """Two enqueue() calls with the same signal_id -> one entry, second returns False."""
    errs: list[str] = []
    _reset_state()
    sig = _make_signal()

    first = retry_queue.enqueue(sig, _UNREACHABLE_URL, "first error")
    second = retry_queue.enqueue(sig, _UNREACHABLE_URL, "second error")

    if first is not True:
        errs.append(f"expected first enqueue to return True, got {first!r}")
    if second is not False:
        errs.append(f"expected second enqueue to return False (dedup), got {second!r}")

    queue = _read_queue()
    if len(queue) != 1:
        errs.append(f"expected exactly 1 entry after dedup, got {len(queue)}: {queue}")

    # Bonus: signal without id should refuse to enqueue
    no_id_signal = {"signal_type": "status"}  # missing id
    third = retry_queue.enqueue(no_id_signal, _UNREACHABLE_URL, "no id")
    if third is not False:
        errs.append(f"expected no-id signal to refuse enqueue, got {third!r}")
    if len(_read_queue()) != 1:
        errs.append("no-id signal should not have added an entry")
    return errs


def case_strict_emit_validation_failure_does_not_enqueue() -> list[str]:
    """Stop-3 contract: validation failures must NOT enqueue (not transient)."""
    errs: list[str] = []
    _reset_state()
    try:
        os.environ["DROPLIST_STRICT_EMIT"] = "1"
        bad = _make_invalid_signal()

        resp = atlas_signal.emit_signal(bad, _UNREACHABLE_URL)
        if resp.get("ok") is not False:
            errs.append(f"expected ok=False for invalid signal, got {resp}")
        if resp.get("error") != "validation_failed":
            errs.append(f"expected error='validation_failed', "
                        f"got {resp.get('error')!r}")

        if _read_queue():
            errs.append(f"expected empty queue (validation failures not retryable), "
                        f"got {_read_queue()}")
    finally:
        os.environ.pop("DROPLIST_STRICT_EMIT", None)
    return errs


def case_4xx_response_does_not_enqueue() -> list[str]:
    """A 400 response is not transient -> emit returns ok=False but queue stays empty."""
    errs: list[str] = []
    _reset_state()
    server, url = _start_server(_400Handler)
    try:
        sig = _make_signal()
        resp = atlas_signal.emit_signal(sig, url)
        if resp.get("ok") is not False:
            errs.append(f"expected ok=False on 400, got {resp}")
        if _read_queue():
            errs.append(f"expected empty queue on 4xx (non-retryable), "
                        f"got {_read_queue()}")
    finally:
        server.shutdown()
        server.server_close()
    return errs


def case_5xx_response_enqueues() -> list[str]:
    """A 503 response IS transient -> emit returns ok=False and queue gains an entry.

    Symmetric counter to (h): the HTTPError code>=500 branch must enqueue.
    A regression in atlas_signal.py:356 (comparator flipped, or enqueue removed
    from this branch) would not be caught by the 4xx-only test.
    """
    errs: list[str] = []
    _reset_state()
    server, url = _start_server(_503Handler)
    try:
        sig = _make_signal()
        resp = atlas_signal.emit_signal(sig, url)
        if resp.get("ok") is not False:
            errs.append(f"expected ok=False on 503, got {resp}")

        queue = _read_queue()
        if len(queue) != 1:
            errs.append(f"expected 1 queued entry on 5xx, got {len(queue)}: {queue}")
            return errs
        entry = queue[0]
        if entry.get("attempts") != 0:
            errs.append(f"expected attempts=0, got {entry.get('attempts')}")
        if entry.get("signal_id") != sig.get("id"):
            errs.append(f"signal_id mismatch: {entry.get('signal_id')!r}")
        if entry.get("url") != url:
            errs.append(f"url mismatch: {entry.get('url')!r}")
    finally:
        server.shutdown()
        server.server_close()
    return errs


def case_drain_via_maybe_emit_signal() -> list[str]:
    """Integration: graph_engine._maybe_emit_atlas_signal drains queued retries.

    (c) tests retry_queue.drain() + manual emit. This case exercises the actual
    production wire site at graph_engine.py:38-61 — the wire that case (c)
    skips. Without it, a regression in the wire's try/except shape (e.g.,
    forgetting to call mark_attempted, or swapping the success bool) would not
    be caught by any retry test.
    """
    from droplist import graph_engine  # local import to avoid module-load order issues

    errs: list[str] = []
    _reset_state()

    server, success_url = _start_server(_CaptureHandler)
    os.environ["DROPLIST_ATLAS_SIGNALS_URL"] = success_url

    original_backoff = retry_queue.BACKOFF_SECONDS[:]
    retry_queue.BACKOFF_SECONDS[:] = [0, 0, 0, 0, 0]

    try:
        # Pre-populate the queue against an unreachable URL
        sig = _make_signal()
        atlas_signal.emit_signal(sig, _UNREACHABLE_URL)
        if len(_read_queue()) != 1:
            errs.append("setup: expected 1 queued entry")
            return errs

        # Redirect the queued entry to the succeeding server and force it due
        entries = _read_queue()
        entries[0]["url"] = success_url
        entries[0]["next_attempt_at"] = "2026-06-08T11:00:00Z"
        retry_queue._atomic_rewrite(entries)

        # Stub DAG (mapper handles missing fields with defaults)
        stub_dag = {
            "dag_id": "DAG-STUB-DRAIN",
            "source_drop": "drop_stub_drain",
            "domain": "general",
            "type": "task",
            "goal": "Stub for drain wire test",
            "status": "complete",
            "nodes": [],
            "entity_refs": [],
            "links": [],
        }
        graph_engine._maybe_emit_atlas_signal(stub_dag)

        # Two POSTs expected: drained retry + the new settle's signal
        if len(_CaptureHandler.received) != 2:
            errs.append(f"expected 2 POSTs (drain + new sig), "
                        f"got {len(_CaptureHandler.received)}")

        # Queue empty after successful drain
        if _read_queue():
            errs.append(f"expected empty queue after drain, got {_read_queue()}")

        success_events = [e for e in _read_events()
                          if e.get("event") == "signal_retry_success"]
        if len(success_events) != 1:
            errs.append(f"expected 1 signal_retry_success event, "
                        f"got {len(success_events)}")
        elif success_events[0].get("signal_id") != sig.get("id"):
            errs.append(f"success event signal_id mismatch: "
                        f"{success_events[0].get('signal_id')!r}")

        # The new settle's atlas_signal_emit event should also be logged
        emit_events = [e for e in _read_events()
                       if e.get("event") == "atlas_signal_emit"
                       and e.get("dag_id") == "DAG-STUB-DRAIN"]
        if len(emit_events) != 1:
            errs.append(f"expected 1 atlas_signal_emit event for stub dag, "
                        f"got {len(emit_events)}")
        elif emit_events[0].get("ok") is not True:
            errs.append(f"expected new settle emit ok=True, "
                        f"got {emit_events[0].get('ok')}")
    finally:
        retry_queue.BACKOFF_SECONDS[:] = original_backoff
        os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)
        server.shutdown()
        server.server_close()
    return errs


# ---------------------------------------------------------------------------
# pytest-style entry points
# ---------------------------------------------------------------------------


def test_first_attempt_success_no_queue_write():
    assert case_first_attempt_success_no_queue_write() == []


def test_failure_enqueues_with_attempts_zero():
    assert case_failure_enqueues_with_attempts_zero() == []


def test_retry_on_next_settle_drains_and_reposts():
    assert case_retry_on_next_settle_drains_and_reposts() == []


def test_max_attempts_exhausted_drops_and_logs():
    assert case_max_attempts_exhausted_drops_and_logs() == []


def test_ttl_pruned_after_seven_days():
    assert case_ttl_pruned_after_seven_days() == []


def test_dedup_by_signal_id():
    assert case_dedup_by_signal_id() == []


def test_strict_emit_validation_failure_does_not_enqueue():
    assert case_strict_emit_validation_failure_does_not_enqueue() == []


def test_4xx_response_does_not_enqueue():
    assert case_4xx_response_does_not_enqueue() == []


def test_5xx_response_enqueues():
    assert case_5xx_response_enqueues() == []


def test_drain_via_maybe_emit_signal():
    assert case_drain_via_maybe_emit_signal() == []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run() -> int:
    print("STOP-4 PKT-006 RETRY BUFFER ACCEPTANCE\n" + "-" * 64)
    cases = [
        ("a. success: no queue write", case_first_attempt_success_no_queue_write),
        ("b. failure: enqueues attempts=0", case_failure_enqueues_with_attempts_zero),
        ("c. retry: drain + replay + retire", case_retry_on_next_settle_drains_and_reposts),
        ("d. exhausted: 5 failures -> drop + log", case_max_attempts_exhausted_drops_and_logs),
        ("e. ttl: 8d -> prune + log", case_ttl_pruned_after_seven_days),
        ("f. dedup: same signal_id -> 1 entry", case_dedup_by_signal_id),
        ("g. strict-mode validation -> no enqueue", case_strict_emit_validation_failure_does_not_enqueue),
        ("h. 4xx response -> no enqueue", case_4xx_response_does_not_enqueue),
        ("i. 5xx response -> enqueue", case_5xx_response_enqueues),
        ("j. drain via _maybe_emit_atlas_signal", case_drain_via_maybe_emit_signal),
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
    print("STOP-4 GATE: PASS" if all_pass else "STOP-4 GATE: FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        code = run()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
