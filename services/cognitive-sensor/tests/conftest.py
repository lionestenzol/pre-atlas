"""
Shared fixtures for atlas module tests.

All fixtures use synthetic data -- no dependency on results.db or memory_db.json.
"""
import sys
import json
import sqlite3
import numpy as np
import pytest
from pathlib import Path

# Add parent directory to sys.path so tests can import atlas_* modules
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def rng():
    """Deterministic random number generator."""
    return np.random.default_rng(42)


@pytest.fixture
def small_embeddings(rng):
    """200 synthetic 384-dim embeddings (float32), mimicking message embeddings."""
    return rng.standard_normal((200, 384)).astype(np.float32)


@pytest.fixture
def small_umap_coords(rng):
    """200 synthetic 2D coordinates, mimicking UMAP output."""
    return rng.standard_normal((200, 2)).astype(np.float64)


@pytest.fixture
def small_labels():
    """200 synthetic HDBSCAN labels: 3 clusters + noise."""
    return np.array(
        [0] * 60 + [1] * 50 + [2] * 40 + [-1] * 50,
        dtype=np.intp,
    )


@pytest.fixture
def small_data(rng):
    """Synthetic data dict matching load_message_data() return shape."""
    n = 200
    convo_ids = [str(i // 10) for i in range(n)]  # 20 conversations
    return {
        "msg_ids": [f"{cid}_{j}" for j, cid in enumerate(convo_ids)],
        "convo_ids": convo_ids,
        "msg_indices": [i % 10 for i in range(n)],
        "roles": ["user" if i % 3 != 2 else "assistant" for i in range(n)],
        "matrix": rng.standard_normal((n, 384)).astype(np.float32),
        "text_lengths": [100 + i for i in range(n)],
        "word_counts": [20 + i % 50 for i in range(n)],
        "titles": [f"Conversation {i // 10}" for i in range(n)],
        "dates": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
    }


@pytest.fixture
def synthetic_db(small_data, tmp_path):
    """
    Create a temporary SQLite database with message_embeddings table
    populated from small_data. Returns the Path to the .db file.
    """
    db_path = tmp_path / "test_results.db"
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE message_embeddings (
            msg_id TEXT PRIMARY KEY,
            convo_id TEXT NOT NULL,
            msg_index INTEGER NOT NULL,
            role TEXT NOT NULL,
            embedding BLOB NOT NULL,
            model TEXT NOT NULL,
            text_length INTEGER NOT NULL,
            word_count INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE convo_titles (
            convo_id TEXT PRIMARY KEY,
            title TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE convo_time (
            convo_id TEXT PRIMARY KEY,
            date TEXT
        )
    """)

    for i in range(len(small_data["msg_ids"])):
        cur.execute(
            "INSERT INTO message_embeddings VALUES (?,?,?,?,?,?,?,?,?)",
            (
                small_data["msg_ids"][i],
                small_data["convo_ids"][i],
                small_data["msg_indices"][i],
                small_data["roles"][i],
                small_data["matrix"][i].tobytes(),
                "test-model",
                small_data["text_lengths"][i],
                small_data["word_counts"][i],
                "2025-01-01T00:00:00",
            ),
        )

    seen_convos = set()
    for i in range(len(small_data["convo_ids"])):
        cid = small_data["convo_ids"][i]
        if cid not in seen_convos:
            seen_convos.add(cid)
            cur.execute(
                "INSERT INTO convo_titles VALUES (?,?)",
                (cid, small_data["titles"][i]),
            )
            cur.execute(
                "INSERT INTO convo_time VALUES (?,?)",
                (cid, small_data["dates"][i]),
            )

    con.commit()
    con.close()
    return db_path


@pytest.fixture
def small_graph_nodes():
    """5 synthetic graph nodes."""
    return [
        {"id": "C0", "cluster_id": 0, "size": 60, "x": 0.0, "y": 0.0, "has_leverage": False},
        {"id": "C1", "cluster_id": 1, "size": 50, "x": 1.0, "y": 1.0, "has_leverage": False},
        {"id": "C2", "cluster_id": 2, "size": 40, "x": -1.0, "y": 1.0, "has_leverage": False},
        {"id": "C3", "cluster_id": 3, "size": 30, "x": 1.0, "y": -1.0, "has_leverage": False},
        {"id": "C4", "cluster_id": 4, "size": 20, "x": -1.0, "y": -1.0, "has_leverage": False},
    ]


@pytest.fixture
def small_graph_edges():
    """6 synthetic graph edges."""
    return [
        {"source": "C0", "target": "C1", "weight": 0.8},
        {"source": "C0", "target": "C2", "weight": 0.6},
        {"source": "C1", "target": "C2", "weight": 0.4},
        {"source": "C1", "target": "C3", "weight": 0.3},
        {"source": "C2", "target": "C4", "weight": 0.5},
        {"source": "C3", "target": "C4", "weight": 0.2},
    ]


@pytest.fixture
def sample_leverage_data():
    """Minimal leverage data dict matching the shape expected by build_graph_data."""
    return {
        "generated": "2025-01-15T10:00:00",
        "clusters_analyzed": 3,
        "clusters": [
            {
                "cluster_id": 0,
                "size": 60,
                "conversations": 5,
                "user_pct": 65.0,
                "normalized_leverage": 8.5,
                "raw_composite": 0.72,
                "tightness": 0.85,
                "execution_ratio": 0.6,
                "reusability_index": 0.35,
                "dependency_load": 0.08,
                "fragmentation_ratio": 0.2,
                "revenue_tag": "productizable_system",
                "market_score": 7,
                "asset_vector": "Framework",
                "top_ngrams": ["system design", "architecture"],
                "central_messages": ["Building the core framework"],
            },
            {
                "cluster_id": 1,
                "size": 50,
                "conversations": 3,
                "user_pct": 55.0,
                "normalized_leverage": 5.2,
                "raw_composite": 0.45,
                "tightness": 0.7,
                "execution_ratio": 0.4,
                "reusability_index": 0.2,
                "dependency_load": 0.1,
                "fragmentation_ratio": 0.3,
                "revenue_tag": "infrastructure_build",
                "market_score": 5,
                "asset_vector": "Tool",
                "top_ngrams": ["api", "endpoint"],
                "central_messages": ["Setting up the API layer"],
            },
        ],
    }


@pytest.fixture
def sample_leverage_file(tmp_path, sample_leverage_data):
    """Write sample leverage data to a JSON file and return the path."""
    path = tmp_path / "leverage_map.json"
    path.write_text(json.dumps(sample_leverage_data), encoding="utf-8")
    return path
