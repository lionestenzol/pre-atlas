"""Tests for the /call gateway's per-capability call counter.

Covers the counter module in isolation (record/get_counts/reset against a
tmp_path store) and the gateway's actual choke point (call_capability records
a row even on an enforcement refusal, since a denied call is still traffic).
"""

from __future__ import annotations

import asyncio

from atlas_map_api import call_counter, gateway
from atlas_map_api.loader import MapSnapshot


def _empty_snapshot(repo_root) -> MapSnapshot:
    return MapSnapshot(
        repo_root=repo_root, generated_at="test", subsystems={}, service_edges=(), retired=frozenset(),
    )


def test_record_creates_and_increments_a_row(tmp_path):
    call_counter.record(tmp_path, "droplist", "list_tasks", "ok")
    call_counter.record(tmp_path, "droplist", "list_tasks", "ok")
    call_counter.record(tmp_path, "droplist", "list_tasks", "error")

    rows = call_counter.get_counts(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["surface"] == "droplist" and row["capability"] == "list_tasks"
    assert row["ok"] == 2 and row["error"] == 1 and row["refused"] == 0
    assert row["first_called"] is not None and row["last_called"] is not None


def test_get_counts_sorts_by_total_desc(tmp_path):
    call_counter.record(tmp_path, "a", "x", "ok")
    for _ in range(5):
        call_counter.record(tmp_path, "b", "y", "ok")

    rows = call_counter.get_counts(tmp_path)
    assert [r["surface"] for r in rows] == ["b", "a"]


def test_counts_persist_across_a_fresh_load(tmp_path):
    call_counter.record(tmp_path, "droplist", "list_tasks", "ok")
    # Force the module cache to miss and re-read from disk.
    call_counter._CACHE = None
    call_counter._CACHE_PATH = None
    rows = call_counter.get_counts(tmp_path)
    assert rows[0]["ok"] == 1


def test_reset_wipes_the_store(tmp_path):
    call_counter.record(tmp_path, "droplist", "list_tasks", "ok")
    call_counter.reset(tmp_path)
    assert call_counter.get_counts(tmp_path) == []


def test_unknown_surface_refusal_still_records_a_row(tmp_path):
    snap = _empty_snapshot(tmp_path)
    result = asyncio.run(
        gateway.call_capability(snap, "no-such-surface", "whatever", None, token=None, role_name="root")
    )
    assert result["refusal"] is True

    rows = call_counter.get_counts(tmp_path)
    assert len(rows) == 1
    assert rows[0]["surface"] == "no-such-surface" and rows[0]["refused"] == 1
