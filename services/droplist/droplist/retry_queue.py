"""PKT-006 retry buffer for failed Atlas signal emissions.

When `emit_signal` hits a transient network error (DNS, timeout, conn refused,
5xx response), the signal lands here instead of evaporating. The next call to
``_maybe_emit_atlas_signal`` drains due entries and re-POSTs them before
emitting the new settle's signal.

Persistence is a JSONL file at ``$DROPLIST_DATA/signal_retry_queue.jsonl``
(honors test tempdir override). All mutations are atomic via
``tempfile.mkstemp + os.replace`` so a crash mid-write can't corrupt the queue.

Doctrine:
  * Dedup by ``signal.id`` — repeated enqueue of the same signal is a no-op.
  * Bounded retries (5) with bounded TTL (7 days). Whichever fires first.
  * Validation failures are NOT retried (handled upstream in ``atlas_signal``).
  * Drain is read-only: callers iterate results and report outcome via
    ``mark_attempted``. This keeps the success/failure write path in one place.

See PKT-006 / BIBLE.md §16 for the upstream contract.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from typing import Any

from . import clock, storage

# ---------------------------------------------------------------------------
# Constants (module-level)
# ---------------------------------------------------------------------------

QUEUE_FILE = "signal_retry_queue.jsonl"
BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200]  # 1m, 5m, 30m, 2h, 12h
MAX_ATTEMPTS = 5
TTL_DAYS = 7

_ERROR_TRUNCATE = 300


# ---------------------------------------------------------------------------
# Low-level file I/O
# ---------------------------------------------------------------------------


def _queue_path() -> str:
    """Always resolve via storage.DATA_DIR so DROPLIST_DATA overrides land here.

    Re-reads storage.DATA_DIR every call: tests sometimes monkeypatch DATA_DIR
    mid-run, and a cached path would point at the previous tempdir.
    """
    return os.path.join(storage.DATA_DIR, QUEUE_FILE)


def _read_entries() -> list[dict[str, Any]]:
    """Read all queue entries. Skip malformed lines (single-writer log,
    but defensive parsing matches storage.read_all)."""
    p = _queue_path()
    if not os.path.exists(p):
        return []
    out: list[dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _atomic_rewrite(entries: list[dict[str, Any]]) -> None:
    """Atomically replace the queue file with the given entries.

    Uses ``tempfile.mkstemp`` in the same directory so ``os.replace`` is atomic
    on every platform (Windows included). Plain truncation would leave a partial
    file behind if the process died mid-write — never acceptable for a queue.
    """
    storage.ensure_data_dir()
    target = _queue_path()
    directory = os.path.dirname(target) or "."

    fd, tmp_path = tempfile.mkstemp(prefix=".retry_queue_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync may fail on some filesystems (e.g. tmpfs in CI);
                # the atomic os.replace below is still correctness-sufficient.
                pass
        os.replace(tmp_path, target)
    except Exception:
        # Clean up the temp file on any failure before re-raising so we don't
        # leak .retry_queue_*.tmp into the data dir.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> _dt.datetime:
    return clock.now()


def _now_iso() -> str:
    return clock.now_iso()


def _add_seconds_iso(seconds: int) -> str:
    """Compute (now + seconds) as ISO UTC string, matching clock.now_iso format."""
    t = _now() + _dt.timedelta(seconds=seconds)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _backoff_for_attempts(attempts: int) -> int:
    """Return the backoff window applicable for the next due-time computation.

    ``attempts=0`` means "just enqueued, hasn't tried yet from the queue" -> 1m.
    After mark_attempted increments to attempts=1, the next due window is 5m,
    etc. Caller must guarantee attempts < MAX_ATTEMPTS before calling.
    """
    idx = min(attempts, len(BACKOFF_SECONDS) - 1)
    return BACKOFF_SECONDS[idx]


def _log_event(event: str, entry: dict[str, Any], **extras: Any) -> None:
    """Append a signal_retry_* event to dag_events.jsonl. Never raises."""
    try:
        record: dict[str, Any] = {
            "event": event,
            "signal_id": entry.get("signal_id"),
            "url": entry.get("url"),
            "attempts": entry.get("attempts"),
            "emitted_at": _now_iso(),
        }
        record.update(extras)
        storage.append(storage.DAG_EVENTS, record)
    except Exception:  # noqa: BLE001 — logging must never break the queue
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enqueue(signal: dict, url: str, error: str) -> bool:
    """Append a failed signal to the retry queue. Dedup by signal_id.

    Returns True if enqueued, False if the signal has no ``id`` (can't dedup,
    so we refuse) or if an entry with the same signal_id is already queued.
    """
    if not isinstance(signal, dict):
        return False
    sig_id = signal.get("id")
    if not sig_id or not isinstance(sig_id, str):
        return False

    entries = _read_entries()
    for e in entries:
        if e.get("signal_id") == sig_id:
            return False

    truncated_error = (error or "")[:_ERROR_TRUNCATE]
    now_iso = _now_iso()
    entry: dict[str, Any] = {
        "signal_id": sig_id,
        "url": url,
        "signal": signal,
        "attempts": 0,
        "first_attempt_at": now_iso,
        "next_attempt_at": _add_seconds_iso(_backoff_for_attempts(0)),
        "last_error": truncated_error,
    }
    entries.append(entry)
    _atomic_rewrite(entries)
    return True


def drain() -> list[dict[str, Any]]:
    """Return entries whose ``next_attempt_at`` is <= now. Does NOT mutate.

    Caller iterates the returned list, re-POSTs each via ``emit_signal``, and
    reports the outcome via ``mark_attempted``.
    """
    now = _now()
    due: list[dict[str, Any]] = []
    for entry in _read_entries():
        nxt = entry.get("next_attempt_at")
        if not isinstance(nxt, str):
            # Defensive: a malformed entry with no schedule should drain so
            # mark_attempted can either retire it or fix it up.
            due.append(entry)
            continue
        t = clock.parse(nxt)
        if t is None or t <= now:
            due.append(entry)
    return due


def mark_attempted(entry: dict, success: bool) -> None:
    """Update queue state based on the retry outcome.

    success=True:
        Remove the entry by signal_id. Log ``signal_retry_success``.

    success=False:
        Increment ``attempts``. If attempts >= MAX_ATTEMPTS, drop the entry AND
        log ``signal_retry_exhausted``. Otherwise recompute ``next_attempt_at``
        from the new backoff window and persist.
    """
    if not isinstance(entry, dict):
        return
    sig_id = entry.get("signal_id")
    if not sig_id:
        return

    entries = _read_entries()
    # Find matching entry by signal_id (the caller's dict may be a snapshot
    # from drain() and not reference-equal to the on-disk record).
    idx = next((i for i, e in enumerate(entries) if e.get("signal_id") == sig_id), None)
    if idx is None:
        # Already dropped (e.g., concurrent prune). Still log the outcome so
        # the audit trail records the attempt regardless.
        if success:
            _log_event("signal_retry_success", entry)
        return

    if success:
        retired = entries.pop(idx)
        _atomic_rewrite(entries)
        _log_event("signal_retry_success", retired)
        return

    target = entries[idx]
    target["attempts"] = int(target.get("attempts", 0)) + 1
    target["last_attempt_at"] = _now_iso()

    if target["attempts"] >= MAX_ATTEMPTS:
        retired = entries.pop(idx)
        _atomic_rewrite(entries)
        _log_event(
            "signal_retry_exhausted",
            retired,
            reason="max_attempts",
            max_attempts=MAX_ATTEMPTS,
        )
        return

    target["next_attempt_at"] = _add_seconds_iso(_backoff_for_attempts(target["attempts"]))
    entries[idx] = target
    _atomic_rewrite(entries)


def prune_expired() -> int:
    """Drop entries older than TTL_DAYS. Log ``signal_retry_pruned`` per drop.

    Returns the count of entries removed.
    """
    entries = _read_entries()
    if not entries:
        return 0

    now = _now()
    keep: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    cutoff_seconds = TTL_DAYS * 86400

    for entry in entries:
        first = entry.get("first_attempt_at")
        t = clock.parse(first) if isinstance(first, str) else None
        if t is None:
            # No first_attempt_at => can't TTL it. Keep so mark_attempted can
            # eventually retire it via MAX_ATTEMPTS.
            keep.append(entry)
            continue
        age = (now - t).total_seconds()
        if age > cutoff_seconds:
            dropped.append(entry)
        else:
            keep.append(entry)

    if not dropped:
        return 0

    _atomic_rewrite(keep)
    for d in dropped:
        _log_event(
            "signal_retry_pruned",
            d,
            reason="ttl_expired",
            ttl_days=TTL_DAYS,
        )
    return len(dropped)
