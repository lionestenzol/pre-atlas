"""Tests for atlas_graph.py -- graph construction with edge strategies and pruning."""
import numpy as np
import pytest
from atlas_graph import build_graph_data, DEFAULT_OVERLAP_MIN, DEFAULT_SIM_MIN, DEFAULT_MAX_EDGES_PER_NODE


def test_returns_nodes_and_edges(small_data, small_labels, small_umap_coords, small_embeddings):
    """Result has 'nodes' and 'edges' keys."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    assert "nodes" in result
    assert "edges" in result
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)


def test_nodes_have_required_keys(small_data, small_labels, small_umap_coords, small_embeddings):
    """Each node dict has the expected keys."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    required = {"id", "cluster_id", "size", "x", "y", "fx", "fy", "has_leverage"}
    for node in result["nodes"]:
        assert required <= set(node.keys()), f"Missing keys in node: {required - set(node.keys())}"


def test_excludes_noise(small_data, small_labels, small_umap_coords, small_embeddings):
    """No node should have cluster_id == -1."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    for node in result["nodes"]:
        assert node["cluster_id"] != -1


def test_node_count_matches_clusters(small_data, small_labels, small_umap_coords, small_embeddings):
    """Number of nodes should equal number of non-noise clusters."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    n_clusters = len(set(small_labels)) - (1 if -1 in small_labels else 0)
    assert len(result["nodes"]) == n_clusters


def test_edge_pruning_cap(small_data, small_labels, small_umap_coords, small_embeddings):
    """No node should appear in more than max_edges_per_node edges."""
    max_k = 2  # use a small cap to force pruning
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
        max_edges_per_node=max_k,
    )
    from collections import Counter
    count = Counter()
    for e in result["edges"]:
        count[e["source"]] += 1
        count[e["target"]] += 1
    for node_id, c in count.items():
        assert c <= max_k, f"Node {node_id} has {c} edges (max={max_k})"


def test_high_overlap_threshold_fewer_edges(small_data, small_labels, small_umap_coords, small_embeddings):
    """Setting overlap_min=0.99 should produce fewer or equal edges."""
    r_normal = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=5,
        overlap_min=0.01,
    )
    r_strict = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=5,
        overlap_min=0.99,
    )
    assert len(r_strict["edges"]) <= len(r_normal["edges"])


def test_high_sim_threshold_fewer_edges(small_data, small_labels, small_umap_coords, small_embeddings):
    """Setting sim_min=0.99 should produce fewer or equal edges."""
    r_normal = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=5,
        sim_min=0.01,
    )
    r_strict = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=5,
        sim_min=0.99,
    )
    assert len(r_strict["edges"]) <= len(r_normal["edges"])


def test_with_leverage(small_data, small_labels, small_umap_coords, small_embeddings, sample_leverage_data):
    """Nodes with matching cluster_id should have has_leverage=True."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=sample_leverage_data, fa2_iterations=10,
    )
    lev_ids = {cl["cluster_id"] for cl in sample_leverage_data["clusters"]}
    for node in result["nodes"]:
        if node["cluster_id"] in lev_ids:
            assert node["has_leverage"] is True
            assert "normalized_leverage" in node
            assert "asset_vector" in node


def test_without_leverage(small_data, small_labels, small_umap_coords, small_embeddings):
    """All nodes should have has_leverage=False when no leverage data."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    for node in result["nodes"]:
        assert node["has_leverage"] is False


def test_edges_have_required_keys(small_data, small_labels, small_umap_coords, small_embeddings):
    """Each edge dict has source, target, weight, type."""
    result = build_graph_data(
        small_data, small_labels, small_umap_coords, small_embeddings,
        leverage_data=None, fa2_iterations=10,
    )
    for edge in result["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "weight" in edge
        assert "type" in edge
        assert edge["type"] in ("overlap", "semantic", "both")


def test_defaults_match_production():
    """Default thresholds match the documented production values."""
    assert DEFAULT_OVERLAP_MIN == 0.15
    assert DEFAULT_SIM_MIN == 0.4
    assert DEFAULT_MAX_EDGES_PER_NODE == 5
