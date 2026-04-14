"""Tests for atlas_data.py -- data loading from SQLite."""
import sqlite3
import numpy as np
import pytest
from atlas_data import load_message_data


def test_load_message_data_returns_correct_shape(synthetic_db):
    """Load from synthetic DB, verify all dict keys and shapes."""
    data = load_message_data(db_path=synthetic_db)
    assert set(data.keys()) == {
        "msg_ids", "convo_ids", "msg_indices", "roles",
        "matrix", "text_lengths", "word_counts", "titles", "dates",
    }
    n = len(data["msg_ids"])
    assert n == 200
    assert len(data["convo_ids"]) == n
    assert len(data["msg_indices"]) == n
    assert len(data["roles"]) == n
    assert len(data["text_lengths"]) == n
    assert len(data["word_counts"]) == n
    assert len(data["titles"]) == n
    assert len(data["dates"]) == n
    assert data["matrix"].shape == (n, 384)


def test_load_message_data_embedding_dtype(synthetic_db):
    """Verify matrix dtype is float32."""
    data = load_message_data(db_path=synthetic_db)
    assert data["matrix"].dtype == np.float32


def test_load_message_data_roles(synthetic_db):
    """Verify roles contain expected values."""
    data = load_message_data(db_path=synthetic_db)
    unique_roles = set(data["roles"])
    assert unique_roles <= {"user", "assistant", "tool"}


def test_load_message_data_titles_not_none(synthetic_db):
    """Verify no title is None (should be '(untitled)' fallback)."""
    data = load_message_data(db_path=synthetic_db)
    for t in data["titles"]:
        assert t is not None


def test_load_message_data_empty_db_exits(tmp_path):
    """Empty DB should cause SystemExit."""
    db_path = tmp_path / "empty.db"
    con = sqlite3.connect(str(db_path))
    con.execute("""
        CREATE TABLE message_embeddings (
            msg_id TEXT PRIMARY KEY,
            convo_id TEXT, msg_index INTEGER, role TEXT,
            embedding BLOB, model TEXT, text_length INTEGER,
            word_count INTEGER, created_at TEXT
        )
    """)
    con.execute("CREATE TABLE convo_titles (convo_id TEXT, title TEXT)")
    con.execute("CREATE TABLE convo_time (convo_id TEXT, date TEXT)")
    con.commit()
    con.close()

    with pytest.raises(SystemExit):
        load_message_data(db_path=db_path)
