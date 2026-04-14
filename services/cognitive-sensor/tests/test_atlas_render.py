"""Tests for atlas_render.py -- HTML generation and payload assembly."""
import json
import numpy as np
import pytest
from pathlib import Path
from atlas_render import load_leverage_data, load_template, build_payload, build_html


class TestLoadLeverageData:
    def test_missing_file_returns_none(self, tmp_path):
        """Nonexistent path returns None."""
        result = load_leverage_data(tmp_path / "does_not_exist.json")
        assert result is None

    def test_valid_file(self, sample_leverage_file):
        """Valid leverage file loads correctly."""
        result = load_leverage_data(sample_leverage_file)
        assert result is not None
        assert "clusters" in result
        assert "cluster_lookup" in result
        assert len(result["clusters"]) == 2

    def test_cluster_lookup_keyed_by_string(self, sample_leverage_file):
        """cluster_lookup keys are strings (for JSON compatibility)."""
        result = load_leverage_data(sample_leverage_file)
        for key in result["cluster_lookup"]:
            assert isinstance(key, str)

    def test_invalid_json_returns_none(self, tmp_path):
        """Malformed JSON returns None."""
        path = tmp_path / "bad.json"
        path.write_text("not json{{{", encoding="utf-8")
        result = load_leverage_data(path)
        assert result is None


class TestLoadTemplate:
    def test_loads_file_content(self, tmp_path):
        """Template file content is returned as string."""
        path = tmp_path / "test.html"
        path.write_text("<html>__DATA_PAYLOAD__</html>", encoding="utf-8")
        result = load_template(path)
        assert "__DATA_PAYLOAD__" in result

    def test_default_template_exists(self):
        """The atlas_template.html file should exist in the service directory."""
        from atlas_render import TEMPLATE_FILE
        assert TEMPLATE_FILE.exists(), f"Template not found: {TEMPLATE_FILE}"


class TestBuildPayload:
    def test_payload_structure(self, small_data, small_labels, small_umap_coords, small_embeddings):
        """Payload has all required top-level keys."""
        layers = {
            "cluster": small_labels.tolist(),
            "role": small_data["roles"],
            "time": [0.5] * len(small_data["roles"]),
            "convo": [0] * len(small_data["roles"]),
        }
        summary = [{"id": 0, "count": 60, "dominant_role": "user",
                     "user_pct": 65.0, "date_range": "", "top_titles": []}]

        payload = build_payload(
            small_data, small_umap_coords, small_labels, layers, summary,
            small_embeddings, leverage_data=None,
            graph_kwargs={"fa2_iterations": 5},
        )

        required_keys = {
            "stats", "x", "y", "convo_ids", "roles", "msg_indices",
            "word_counts", "titleLookup", "dateLookup", "layers",
            "cluster_summary", "leverage", "graph",
        }
        assert required_keys <= set(payload.keys())

    def test_payload_stats(self, small_data, small_labels, small_umap_coords, small_embeddings):
        """Stats contain correct counts."""
        layers = {
            "cluster": small_labels.tolist(),
            "role": small_data["roles"],
            "time": [0.5] * 200,
            "convo": [0] * 200,
        }
        payload = build_payload(
            small_data, small_umap_coords, small_labels, layers, [],
            small_embeddings, graph_kwargs={"fa2_iterations": 5},
        )
        assert payload["stats"]["total"] == 200

    def test_payload_serializable(self, small_data, small_labels, small_umap_coords, small_embeddings):
        """Payload can be serialized to JSON."""
        layers = {
            "cluster": small_labels.tolist(),
            "role": small_data["roles"],
            "time": [0.5] * 200,
            "convo": [0] * 200,
        }
        payload = build_payload(
            small_data, small_umap_coords, small_labels, layers, [],
            small_embeddings, graph_kwargs={"fa2_iterations": 5},
        )
        result = json.dumps(payload, ensure_ascii=False)
        assert len(result) > 0
        # Verify round-trip
        parsed = json.loads(result)
        assert parsed["stats"]["total"] == 200


class TestBuildHtml:
    def test_writes_file(self, small_data, small_labels, small_umap_coords, small_embeddings, tmp_path):
        """HTML file is created at the specified path."""
        template = tmp_path / "template.html"
        template.write_text(
            "<!doctype html><script>const D = __DATA_PAYLOAD__;</script>__SUBTITLE__",
            encoding="utf-8",
        )
        out_file = tmp_path / "output.html"

        layers = {
            "cluster": small_labels.tolist(),
            "role": small_data["roles"],
            "time": [0.5] * 200,
            "convo": [0] * 200,
        }
        summary = []

        build_html(
            small_data, small_umap_coords, small_labels, layers, summary,
            small_embeddings,
            out_file=out_file, template_path=template,
            leverage_path=tmp_path / "no_leverage.json",
            graph_kwargs={"fa2_iterations": 5},
        )

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "__DATA_PAYLOAD__" not in content
        assert "__SUBTITLE__" not in content
        assert "const D = " in content

    def test_payload_parseable_from_html(self, small_data, small_labels, small_umap_coords, small_embeddings, tmp_path):
        """
        The JSON payload embedded in the HTML can be extracted and parsed.
        This is the exact contract that cluster_leverage_map.py depends on.
        """
        template = tmp_path / "template.html"
        template.write_text(
            "<!doctype html><script>const D = __DATA_PAYLOAD__;</script>__SUBTITLE__",
            encoding="utf-8",
        )
        out_file = tmp_path / "output.html"

        layers = {
            "cluster": small_labels.tolist(),
            "role": small_data["roles"],
            "time": [0.5] * 200,
            "convo": [0] * 200,
        }

        build_html(
            small_data, small_umap_coords, small_labels, layers, [],
            small_embeddings,
            out_file=out_file, template_path=template,
            leverage_path=tmp_path / "no_leverage.json",
            graph_kwargs={"fa2_iterations": 5},
        )

        content = out_file.read_text(encoding="utf-8")
        marker = "const D = "
        start = content.index(marker) + len(marker)
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(content, start)

        # Verify downstream contract fields
        assert "layers" in payload
        assert "cluster" in payload["layers"]
        assert "convo_ids" in payload
        assert "roles" in payload
        assert "word_counts" in payload
        assert "msg_indices" in payload
        assert len(payload["layers"]["cluster"]) == 200
