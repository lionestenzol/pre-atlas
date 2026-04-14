"""Tests for atlas_layers.py -- layer building and cluster summary."""
import numpy as np
import pytest
from atlas_layers import build_layers, build_cluster_summary


class TestBuildLayers:
    def test_returns_correct_keys(self, small_data, small_labels):
        """Return dict has all 4 layer keys."""
        layers = build_layers(small_data, small_labels)
        assert set(layers.keys()) == {"cluster", "role", "time", "convo"}

    def test_correct_lengths(self, small_data, small_labels):
        """Each layer list has length matching input."""
        layers = build_layers(small_data, small_labels)
        n = len(small_data["convo_ids"])
        assert len(layers["cluster"]) == n
        assert len(layers["role"]) == n
        assert len(layers["time"]) == n
        assert len(layers["convo"]) == n

    def test_cluster_matches_labels(self, small_data, small_labels):
        """Cluster layer should match labels.tolist()."""
        layers = build_layers(small_data, small_labels)
        assert layers["cluster"] == small_labels.tolist()

    def test_role_matches_data(self, small_data, small_labels):
        """Role layer should be the same list as input roles."""
        layers = build_layers(small_data, small_labels)
        assert layers["role"] == small_data["roles"]

    def test_time_normalization(self, small_data, small_labels):
        """All time values should be in [0.0, 1.0]."""
        layers = build_layers(small_data, small_labels)
        for t in layers["time"]:
            assert 0.0 <= t <= 1.0, f"time value {t} out of range"

    def test_time_has_extremes(self, small_data, small_labels):
        """Should have values at or near 0.0 and 1.0."""
        layers = build_layers(small_data, small_labels)
        assert min(layers["time"]) == pytest.approx(0.0, abs=0.01)
        assert max(layers["time"]) == pytest.approx(1.0, abs=0.01)

    def test_time_no_dates_defaults(self, small_data, small_labels):
        """When all dates are empty, time values should all be 0.5."""
        data = {**small_data, "dates": [""] * len(small_data["dates"])}
        layers = build_layers(data, small_labels)
        assert all(t == 0.5 for t in layers["time"])

    def test_convo_values_are_mod50(self, small_data, small_labels):
        """Convo values should be int(convo_id) % 50."""
        layers = build_layers(small_data, small_labels)
        for i, cid in enumerate(small_data["convo_ids"]):
            assert layers["convo"][i] == int(cid) % 50


class TestBuildClusterSummary:
    def test_sorted_by_count(self, small_data, small_labels):
        """Summary should be sorted by descending message count."""
        summary = build_cluster_summary(small_data, small_labels)
        counts = [s["count"] for s in summary]
        assert counts == sorted(counts, reverse=True)

    def test_excludes_noise(self, small_data, small_labels):
        """No summary entry should have id == -1."""
        summary = build_cluster_summary(small_data, small_labels)
        ids = [s["id"] for s in summary]
        assert -1 not in ids

    def test_user_pct_range(self, small_data, small_labels):
        """user_pct should be between 0 and 100."""
        summary = build_cluster_summary(small_data, small_labels)
        for s in summary:
            assert 0 <= s["user_pct"] <= 100

    def test_top_titles_max_3(self, small_data, small_labels):
        """Each entry should have at most 3 top_titles."""
        summary = build_cluster_summary(small_data, small_labels)
        for s in summary:
            assert len(s["top_titles"]) <= 3

    def test_has_required_fields(self, small_data, small_labels):
        """Each summary entry has all required fields."""
        summary = build_cluster_summary(small_data, small_labels)
        required = {"id", "count", "dominant_role", "user_pct", "date_range", "top_titles"}
        for s in summary:
            assert required <= set(s.keys())

    def test_cluster_count_matches(self, small_data, small_labels):
        """Number of summary entries should match number of non-noise clusters."""
        summary = build_cluster_summary(small_data, small_labels)
        n_clusters = len(set(small_labels)) - (1 if -1 in small_labels else 0)
        assert len(summary) == n_clusters

    def test_total_count_matches(self, small_data, small_labels):
        """Sum of counts should equal number of non-noise messages."""
        summary = build_cluster_summary(small_data, small_labels)
        total = sum(s["count"] for s in summary)
        expected = int(np.sum(small_labels != -1))
        assert total == expected
