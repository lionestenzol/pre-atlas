"""Shared fixtures for Optogon tests."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a tmp file for isolated tests."""
    from optogon import config, session_store
    db = tmp_path / "test_sessions.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    # Reset the singleton
    session_store._default_store = None  # type: ignore[attr-defined]
    yield db
    session_store._default_store = None  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _clear_signals():
    from optogon import signals
    signals.clear()
    yield
    signals.clear()
