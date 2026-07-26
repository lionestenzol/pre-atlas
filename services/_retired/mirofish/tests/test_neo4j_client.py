"""Tests for mirofish.graph.neo4j_client — allowlist validation (no Neo4j needed)."""
import pytest

from mirofish.graph.neo4j_client import (
    Neo4jClient,
    VALID_NODE_LABELS,
    VALID_EDGE_LABELS,
)


class TestAllowlistValidation:
    """Test that invalid Cypher labels are rejected before reaching the database."""

    def setup_method(self):
        # Don't connect to real Neo4j — we're testing validation before the query
        self.client = Neo4jClient(uri="bolt://fake:7687")

    @pytest.mark.asyncio
    async def test_upsert_node_rejects_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid node type"):
            await self.client.upsert_node("test", "INJECTION_LABEL", "desc")

    @pytest.mark.asyncio
    async def test_upsert_node_accepts_valid_types(self):
        for label in VALID_NODE_LABELS:
            # Will fail at the driver level (no real Neo4j), but should NOT raise ValueError
            with pytest.raises(Exception) as exc_info:
                await self.client.upsert_node("test", label, "desc")
            assert "Invalid node type" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upsert_edge_rejects_invalid_source_type(self):
        with pytest.raises(ValueError, match="Invalid source type"):
            await self.client.upsert_edge("a", "BAD", "b", "Concept", "SUPPORTS")

    @pytest.mark.asyncio
    async def test_upsert_edge_rejects_invalid_target_type(self):
        with pytest.raises(ValueError, match="Invalid target type"):
            await self.client.upsert_edge("a", "Concept", "b", "BAD", "SUPPORTS")

    @pytest.mark.asyncio
    async def test_upsert_edge_rejects_invalid_edge_type(self):
        with pytest.raises(ValueError, match="Invalid edge type"):
            await self.client.upsert_edge("a", "Concept", "b", "Concept", "DROP_DATABASE")

    def test_valid_labels_match_expected(self):
        assert VALID_NODE_LABELS == {"Concept", "Person", "Argument", "Evidence", "Claim"}
        assert VALID_EDGE_LABELS == {"SUPPORTS", "CONTRADICTS", "RELATED_TO", "AUTHORED_BY"}
