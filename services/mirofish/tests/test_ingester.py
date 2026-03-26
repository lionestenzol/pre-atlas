"""Tests for mirofish.graph.ingester — full pipeline with mocked dependencies."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from mirofish.graph.ingester import DocumentIngester
from mirofish.graph.extractor import ExtractionResult, Entity, Relationship


class TestDocumentIngester:
    @pytest.mark.asyncio
    async def test_ingest_pipeline_flow(self):
        """Verify the full pipeline: chunk -> embed -> extract -> write."""
        # Mock dependencies
        mock_neo4j = AsyncMock()
        mock_embedder = AsyncMock()
        mock_extractor = AsyncMock()

        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
        mock_extractor.extract.return_value = ExtractionResult(
            entities=[
                Entity(name="AI", type="Concept", description="Artificial intelligence"),
                Entity(name="ML", type="Concept", description="Machine learning"),
            ],
            relationships=[
                Relationship(source="ML", target="AI", type="SUPPORTS", evidence="ML is a subset of AI"),
            ],
        )
        mock_neo4j.upsert_node.return_value = "node-id-1"

        ingester = DocumentIngester(
            neo4j=mock_neo4j,
            embedder=mock_embedder,
            extractor=mock_extractor,
        )

        result = await ingester.ingest_document("A short document about AI and ML.", chunk_size=500)

        # Should have processed 1 chunk (text is short)
        assert result["chunks"] == 1
        assert result["entities"] == 2
        assert result["relationships"] == 1

        # Verify calls
        mock_neo4j.ensure_schema.assert_awaited_once()
        mock_embedder.embed.assert_awaited_once()
        mock_extractor.extract.assert_awaited_once()
        assert mock_neo4j.upsert_node.await_count == 2
        assert mock_neo4j.upsert_edge.await_count == 1

    @pytest.mark.asyncio
    async def test_ingest_empty_document(self):
        """Empty document produces zero chunks."""
        mock_neo4j = AsyncMock()
        mock_embedder = AsyncMock()
        mock_extractor = AsyncMock()

        ingester = DocumentIngester(
            neo4j=mock_neo4j,
            embedder=mock_embedder,
            extractor=mock_extractor,
        )

        result = await ingester.ingest_document("")

        assert result["chunks"] == 0
        assert result["entities"] == 0
        assert result["relationships"] == 0
        # Schema still ensured even for empty doc
        mock_neo4j.ensure_schema.assert_awaited_once()
        # No embed or extract calls
        mock_embedder.embed.assert_not_awaited()
        mock_extractor.extract.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ingest_entity_types_passed_to_edges(self):
        """Edge upsert should use correct entity types from extraction."""
        mock_neo4j = AsyncMock()
        mock_embedder = AsyncMock()
        mock_extractor = AsyncMock()

        mock_embedder.embed.return_value = [0.5]
        mock_extractor.extract.return_value = ExtractionResult(
            entities=[
                Entity(name="Turing", type="Person", description="Mathematician"),
                Entity(name="Halting Problem", type="Argument", description="Undecidability"),
            ],
            relationships=[
                Relationship(source="Turing", target="Halting Problem", type="AUTHORED_BY", evidence="1936 paper"),
            ],
        )

        ingester = DocumentIngester(
            neo4j=mock_neo4j,
            embedder=mock_embedder,
            extractor=mock_extractor,
        )

        await ingester.ingest_document("Turing proved the halting problem undecidable.")

        # Check that edge uses Person and Argument types
        mock_neo4j.upsert_edge.assert_awaited_once_with(
            source_name="Turing",
            source_type="Person",
            target_name="Halting Problem",
            target_type="Argument",
            edge_type="AUTHORED_BY",
            evidence="1936 paper",
        )
