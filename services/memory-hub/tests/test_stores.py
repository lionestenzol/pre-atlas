"""Unit tests for store backends. No live dependencies — only file reads."""

from __future__ import annotations

import json

from memory_hub import stores
from memory_hub.schemas import MemoryHit


def test_overlap_score_basic():
    assert stores._overlap_score(set(), {"a", "b"}) == 0.0
    assert stores._overlap_score({"foo"}, {"foo"}) == 1.0
    s = stores._overlap_score({"foo", "bar"}, {"foo", "baz"})
    assert 0 < s < 1


def test_tokens_strip_stopwords():
    toks = stores._tokens("the search stack is for the agent")
    assert "search" in toks
    assert "stack" in toks
    assert "agent" in toks
    assert "the" not in toks
    assert "is" not in toks
    assert "for" not in toks


def test_droplist_empty_query_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(stores, "DROPLIST_PACKETS", tmp_path / "packets.jsonl")
    (tmp_path / "packets.jsonl").write_text("", encoding="utf-8")
    assert stores.search_droplist("", 5) == []
    assert stores.search_droplist("   ", 5) == []


def test_droplist_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(stores, "DROPLIST_PACKETS", tmp_path / "does-not-exist.jsonl")
    assert stores.search_droplist("anything", 5) == []


def test_droplist_finds_matching_packet(tmp_path, monkeypatch):
    packets_file = tmp_path / "packets.jsonl"
    monkeypatch.setattr(stores, "DROPLIST_PACKETS", packets_file)
    packets_file.write_text(
        json.dumps({"drop_id": "drop_abc", "normalized_input": "build the ultimate search stack", "type": "build", "domain": "tools"}) + "\n" +
        json.dumps({"drop_id": "drop_xyz", "normalized_input": "grocery shopping for the week", "type": "admin", "domain": "home"}) + "\n",
        encoding="utf-8",
    )
    hits = stores.search_droplist("ultimate search", k=5)
    assert len(hits) == 1
    assert hits[0].canonical_id == "drop_abc"
    assert hits[0].type == "build"
    assert hits[0].relevance > 0


def test_idea_registry_real_shape_execute_now_and_next_up(tmp_path, monkeypatch):
    """Real idea_registry.json uses {metadata, execute_now: [...], next_up: [...]}
    — the OLD provider was looking for data['ideas'] and getting [] every time."""
    registry_file = tmp_path / "registry.json"
    monkeypatch.setattr(stores, "IDEA_REGISTRY", registry_file)
    registry_file.write_text(
        json.dumps({
            "metadata": {"generated": "now"},
            "execute_now": [
                {"canonical_id": "canon_001", "canonical_title": "Build Search Stack", "category": "build", "priority_score": 0.9, "mention_count": 12},
                {"canonical_id": "canon_002", "canonical_title": "Power Dynamics Book", "category": "writing", "priority_score": 0.7, "mention_count": 8},
            ],
            "next_up": [
                {"canonical_id": "canon_003", "canonical_title": "Search Stack Phase 4", "category": "build", "priority_score": 0.6, "mention_count": 4},
            ],
        }),
        encoding="utf-8",
    )
    hits = stores.search_idea_registry("search stack", k=5)
    canonical_ids = {h.canonical_id for h in hits}
    assert "canon_001" in canonical_ids
    assert "canon_003" in canonical_ids
    assert "canon_002" not in canonical_ids


def test_lookup_idea_returns_idea_with_bucket(tmp_path, monkeypatch):
    registry_file = tmp_path / "registry.json"
    monkeypatch.setattr(stores, "IDEA_REGISTRY", registry_file)
    registry_file.write_text(
        json.dumps({
            "execute_now": [{"canonical_id": "canon_001", "canonical_title": "A"}],
            "next_up": [{"canonical_id": "canon_002", "canonical_title": "B"}],
        }),
        encoding="utf-8",
    )
    idea = stores.lookup_idea("canon_002")
    assert idea is not None
    assert idea["_bucket"] == "next_up"
    assert idea["canonical_title"] == "B"

    assert stores.lookup_idea("nonexistent") is None


def test_append_to_droplist_writes_valid_packet(tmp_path, monkeypatch):
    packets_file = tmp_path / "packets.jsonl"
    monkeypatch.setattr(stores, "DROPLIST_PACKETS", packets_file)
    record = stores.append_to_droplist(
        packet_type="intel_drop",
        content="external article found",
        source="n8n.daily-intel",
        metadata={"query": "anthropic", "url": "https://example.com"},
    )
    assert record["drop_id"].startswith("drop_")
    assert record["type"] == "intel_drop"
    assert record["normalized_input"] == "external article found"

    written = packets_file.read_text(encoding="utf-8").strip()
    parsed = json.loads(written)
    assert parsed["drop_id"] == record["drop_id"]


def test_store_status_returns_all_four():
    statuses = stores.store_status()
    names = {s.name for s in statuses}
    assert names == {"droplist", "idea_registry", "cognitive_sensor", "mirofish_neo4j"}
