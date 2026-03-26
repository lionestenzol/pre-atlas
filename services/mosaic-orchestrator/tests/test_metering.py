"""Tests for the metering module."""
import pytest
from pathlib import Path
from mosaic.metering.metering import MeteringStore


@pytest.fixture
def metering(tmp_path):
    """Fresh metering store with 3600s free tier."""
    return MeteringStore(tmp_path / "metering.db", free_tier_seconds=3600)


def test_initial_usage_is_zero(metering):
    usage = metering.get_usage()
    assert usage["ai_seconds_used"] == 0
    assert usage["free_tier_seconds"] == 3600
    assert usage["remaining_seconds"] == 3600
    assert usage["paused"] is False
    assert usage["over_limit"] is False


def test_record_and_retrieve_usage(metering):
    metering.record_usage(10.5, 1000, "claude", "task_1")
    metering.record_usage(5.0, 500, "ollama", "task_2")
    usage = metering.get_usage()
    assert usage["ai_seconds_used"] == 15.5
    assert usage["total_tokens"] == 1500
    assert usage["total_events"] == 2
    assert usage["remaining_seconds"] == 3584.5


def test_pause_and_resume(metering):
    assert metering.is_paused() is False
    metering.pause()
    assert metering.is_paused() is True
    metering.resume()
    assert metering.is_paused() is False


def test_over_limit_detection(metering):
    metering.record_usage(3600.0, 100000, "claude", "big_task")
    usage = metering.get_usage()
    assert usage["over_limit"] is True
    assert usage["remaining_seconds"] == 0


def test_multiple_stores_same_db(tmp_path):
    """Two store instances on the same DB should see each other's data."""
    db = tmp_path / "shared.db"
    store1 = MeteringStore(db, free_tier_seconds=3600)
    store1.record_usage(100.0, 5000, "claude", "task_a")

    store2 = MeteringStore(db, free_tier_seconds=3600)
    usage = store2.get_usage()
    assert usage["ai_seconds_used"] == 100.0
