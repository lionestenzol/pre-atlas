"""Signal emit + transport tests · Ship Target #1.

Covers:
  - emit() always validates and stores locally.
  - SIGNAL_EMIT_ENABLED gate: off -> never POST; on -> POST.
  - Fail-soft transport: connection error never raises out of emit().
"""
from __future__ import annotations
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from optogon import config, signals


class _CapturingHandler(BaseHTTPRequestHandler):
    """Captures POST bodies into a class-level list."""
    posted: list[bytes] = []

    def do_GET(self):  # noqa: N802
        if self.path == "/api/auth/token":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"token":"test-token"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b""
        _CapturingHandler.posted.append(body)
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true,"signal_id":"sig_test"}')

    def log_message(self, *_args, **_kw):  # silence stderr
        return


@pytest.fixture
def fake_delta_kernel(monkeypatch):
    _CapturingHandler.posted = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(config, "DELTA_KERNEL_URL", f"http://127.0.0.1:{port}")
    signals._reset_token_for_tests()
    yield _CapturingHandler.posted, port
    server.shutdown()
    server.server_close()


def _wait_for_post(posted_list, timeout=2.0):
    """Wait up to `timeout` seconds for at least one POST."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if posted_list:
            return True
        time.sleep(0.01)
    return False


def test_emit_always_validates_and_stores_locally():
    sig = signals.emit(
        source_layer="optogon",
        signal_type="status",
        priority="low",
        label="emit-test",
        summary="local-only",
    )
    assert sig["id"].startswith("sig_")
    assert signals.all_signals() == [sig]


def test_emit_does_not_post_when_switch_off(monkeypatch, fake_delta_kernel):
    posted, _ = fake_delta_kernel
    monkeypatch.setattr(config, "SIGNAL_EMIT_ENABLED", False)
    signals.emit(
        source_layer="optogon",
        signal_type="status",
        priority="low",
        label="off",
        summary="should not POST",
    )
    # Give the daemon thread (if any) a chance to run.
    assert not _wait_for_post(posted, timeout=0.3), "no POST expected when switch is off"


def test_emit_posts_when_switch_on(monkeypatch, fake_delta_kernel):
    posted, _ = fake_delta_kernel
    monkeypatch.setattr(config, "SIGNAL_EMIT_ENABLED", True)
    signals.emit(
        source_layer="optogon",
        signal_type="completion",
        priority="normal",
        label="on",
        summary="should POST to delta-kernel",
        task_id="t_test",
    )
    assert _wait_for_post(posted, timeout=2.0), "expected at least one POST"
    body = posted[0]
    import json
    parsed = json.loads(body)
    assert parsed["signal_type"] == "completion"
    assert parsed["payload"]["label"] == "on"
    assert parsed["schema_version"] == "1.0"


def test_emit_failsoft_when_delta_kernel_down(monkeypatch):
    """Delta-kernel unreachable must not raise from emit()."""
    monkeypatch.setattr(config, "DELTA_KERNEL_URL", "http://127.0.0.1:1")  # closed port
    monkeypatch.setattr(config, "SIGNAL_EMIT_ENABLED", True)
    signals._reset_token_for_tests()
    sig = signals.emit(
        source_layer="optogon",
        signal_type="error",
        priority="urgent",
        label="failsoft",
        summary="delta-kernel down",
        action_required=True,
        action_options=[
            {"id": "retry", "label": "Retry", "risk_tier": "low"},
        ],
    )
    # Should still return locally even though POST fails on background thread.
    assert sig["id"] in {s["id"] for s in signals.all_signals()}
    # Give the background thread time to fail and log.
    import time
    time.sleep(0.2)
