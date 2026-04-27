"""Signal emitter - builds Signal.v1 payloads to send to InPACT.

Phase 3 (Ship Target #1): payloads now POST to delta-kernel's
``/api/signals`` endpoint when ``OPTOGON_SIGNAL_EMIT=1``. Transport is
fail-soft: any HTTP failure is swallowed (logged) so a delta-kernel
outage never crashes a path. The local in-memory list is preserved
for tests and the ``/session/{id}/signals`` debug surface.
"""
from __future__ import annotations
import json
import logging
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from . import config
from .contract_validator import validate


_logger = logging.getLogger(__name__)
_signals: list[dict[str, Any]] = []
_lock = threading.RLock()
_token: Optional[str] = None
_token_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_token() -> Optional[str]:
    """Fetch and cache a delta-kernel auth token. Returns None on failure."""
    global _token
    if _token:
        return _token
    with _token_lock:
        if _token:
            return _token
        url = f"{config.DELTA_KERNEL_URL}/api/auth/token"
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                tok = body.get("token") if isinstance(body, dict) else None
                if isinstance(tok, str) and tok:
                    _token = tok
                    return _token
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            _logger.debug("optogon.signals: token fetch failed: %s", exc)
        return None


def _post_to_delta_kernel(signal: dict[str, Any]) -> None:
    """Fire-and-forget POST to delta-kernel. Always returns; never raises."""
    if not config.SIGNAL_EMIT_ENABLED:
        return
    url = f"{config.DELTA_KERNEL_URL}/api/signals"
    data = json.dumps(signal).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = _fetch_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            status = resp.status
            if status >= 400:
                _logger.warning("optogon.signals: delta-kernel returned %s for %s", status, signal["id"])
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Fail-soft: delta-kernel may be down; never raise from emit().
        _logger.info("optogon.signals: POST to %s failed (%s); signal %s held locally", url, exc, signal["id"])


def emit(
    source_layer: str,
    signal_type: str,
    priority: str,
    label: str,
    summary: str,
    data: Optional[dict[str, Any]] = None,
    action_required: bool = False,
    action_options: Optional[list[dict[str, Any]]] = None,
    task_id: Optional[str] = None,
) -> dict[str, Any]:
    signal = {
        "schema_version": "1.0",
        "id": f"sig_{uuid.uuid4().hex[:12]}",
        "emitted_at": _now(),
        "source_layer": source_layer,
        "signal_type": signal_type,
        "priority": priority,
        "payload": {
            "task_id": task_id,
            "label": label,
            "summary": summary,
            "data": data or {},
            "action_required": action_required,
            "action_options": action_options or [],
        },
    }
    # Signal.v1 conditional: action_required=true requires non-empty action_options
    if not action_required:
        # Remove the empty array so it passes validation cleanly
        signal["payload"].pop("action_options", None)
    validate(signal, "Signal")
    with _lock:
        _signals.append(signal)

    # Fire-and-forget POST. Threaded so we don't block the path runtime
    # on a slow delta-kernel response.
    if config.SIGNAL_EMIT_ENABLED:
        thread = threading.Thread(target=_post_to_delta_kernel, args=(signal,), daemon=True)
        thread.start()
    return signal


def all_signals(since: Optional[str] = None) -> list[dict[str, Any]]:
    with _lock:
        if since is None:
            return list(_signals)
        return [s for s in _signals if s["emitted_at"] > since]


def clear() -> None:
    """Test helper."""
    with _lock:
        _signals.clear()


def _reset_token_for_tests() -> None:
    """Test helper. Forces the next emit() to refetch the token."""
    global _token
    _token = None
