"""Tests for mirofish.reports.export."""
import pytest
import jsonschema

from mirofish.reports.export import to_json, to_markdown


class TestToJson:
    def test_valid_report_passes(self, sample_report):
        result = to_json(sample_report)
        assert result["simulation_id"] == "sim-test-001"
        assert result["schema_version"] == "1.0.0"

    def test_invalid_report_raises(self):
        bad = {"simulation_id": "x"}  # missing required fields
        with pytest.raises(jsonschema.ValidationError):
            to_json(bad)

    def test_extra_field_rejected(self, sample_report):
        sample_report["unexpected_field"] = "bad"
        with pytest.raises(jsonschema.ValidationError):
            to_json(sample_report)


class TestToMarkdown:
    def test_contains_expected_sections(self, sample_report):
        md = to_markdown(sample_report)
        assert "# Simulation Report:" in md
        assert "## Summary" in md
        assert "## Key Insights" in md
        assert "## Consensus Points" in md
        assert "## Points of Dissent" in md
        assert "## Recommendations" in md
        assert "## Agent Contributions" in md

    def test_agent_table_present(self, sample_report):
        md = to_markdown(sample_report)
        assert "| Agent |" in md
        assert "agent_000" in md
        assert "Expert" in md

    def test_minimal_report(self):
        minimal = {
            "topic": "minimal",
            "simulation_id": "sim-min",
            "summary": "Brief.",
        }
        md = to_markdown(minimal)
        assert "# Simulation Report: minimal" in md
        assert "## Summary" in md
        # Optional sections should not appear
        assert "## Key Insights" not in md
