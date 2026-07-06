"""Tests for mirofish.graph.extractor."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mirofish.graph.extractor import (
    EntityExtractor,
    ExtractionResult,
    Entity,
    Relationship,
    VALID_NODE_TYPES,
    VALID_EDGE_TYPES,
)


class TestParseResponse:
    """Test _parse_response — pure function, no Ollama needed."""

    def setup_method(self):
        self.extractor = EntityExtractor(ollama_url="http://fake:11434")

    def test_valid_json(self):
        raw = json.dumps({
            "entities": [
                {"name": "AI", "type": "Concept", "description": "Artificial intelligence"},
                {"name": "Turing", "type": "Person", "description": "Computer scientist"},
            ],
            "relationships": [
                {"source": "Turing", "target": "AI", "type": "AUTHORED_BY", "evidence": "Turing test"},
            ],
        })
        result = self.extractor._parse_response(raw)
        assert len(result.entities) == 2
        assert result.entities[0].name == "AI"
        assert result.entities[0].type == "Concept"
        assert len(result.relationships) == 1
        assert result.relationships[0].type == "AUTHORED_BY"

    def test_invalid_entity_type_defaults_to_concept(self):
        raw = json.dumps({
            "entities": [{"name": "X", "type": "INVALID_TYPE", "description": "test"}],
            "relationships": [],
        })
        result = self.extractor._parse_response(raw)
        assert result.entities[0].type == "Concept"

    def test_invalid_edge_type_defaults_to_related(self):
        raw = json.dumps({
            "entities": [],
            "relationships": [{"source": "A", "target": "B", "type": "INVALID_REL", "evidence": ""}],
        })
        result = self.extractor._parse_response(raw)
        assert result.relationships[0].type == "RELATED_TO"

    def test_malformed_json_with_embedded_object(self):
        raw = 'Here is the result: {"entities": [{"name": "X", "type": "Concept", "description": "test"}], "relationships": []} some trailing text'
        result = self.extractor._parse_response(raw)
        assert len(result.entities) == 1

    def test_completely_invalid_returns_empty(self):
        result = self.extractor._parse_response("not json at all")
        assert result.entities == []
        assert result.relationships == []

    def test_missing_name_skips_entity(self):
        raw = json.dumps({
            "entities": [
                {"type": "Concept", "description": "no name"},
                {"name": "Valid", "type": "Concept", "description": "has name"},
            ],
            "relationships": [],
        })
        result = self.extractor._parse_response(raw)
        assert len(result.entities) == 1
        assert result.entities[0].name == "Valid"

    def test_missing_source_or_target_skips_relationship(self):
        raw = json.dumps({
            "entities": [],
            "relationships": [
                {"source": "A", "type": "SUPPORTS"},  # missing target
                {"source": "A", "target": "B", "type": "SUPPORTS", "evidence": "ok"},
            ],
        })
        result = self.extractor._parse_response(raw)
        assert len(result.relationships) == 1

    def test_empty_entities_and_relationships(self):
        raw = json.dumps({"entities": [], "relationships": []})
        result = self.extractor._parse_response(raw)
        assert result.entities == []
        assert result.relationships == []


class TestExtractWithMock:
    @pytest.mark.asyncio
    async def test_extract_falls_back_on_connection_error(self):
        """When Ollama is unreachable, extract returns empty result gracefully."""
        extractor = EntityExtractor(ollama_url="http://localhost:99999")
        result = await extractor.extract("Test text about AI and machine learning")
        assert isinstance(result, ExtractionResult)
        assert result.entities == []
