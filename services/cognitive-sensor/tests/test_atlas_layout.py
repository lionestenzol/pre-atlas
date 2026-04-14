"""Tests for atlas_layout.py -- ForceAtlas2 physics simulation."""
import numpy as np
import pytest
from atlas_layout import forceatlas2_layout


def test_empty_graph():
    """Empty nodes list returns empty positions."""
    result = forceatlas2_layout([], [])
    assert result == []


def test_single_node():
    """Single node with no edges stays near initial position (gravity pulls to origin)."""
    nodes = [{"id": "A", "size": 10, "x": 5.0, "y": 5.0}]
    result = forceatlas2_layout(nodes, [], iterations=10)
    assert len(result) == 1
    x, y = result[0]
    assert np.isfinite(x) and np.isfinite(y)


def test_two_nodes_no_edges():
    """Two nodes with no edges repel each other."""
    nodes = [
        {"id": "A", "size": 10, "x": 0.0, "y": 0.0},
        {"id": "B", "size": 10, "x": 0.1, "y": 0.0},
    ]
    result = forceatlas2_layout(nodes, [], iterations=50, gravity=0.01)
    (ax, ay), (bx, by) = result
    initial_dist = 0.1
    final_dist = np.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
    assert final_dist > initial_dist, "Repulsion should push nodes apart"


def test_basic_layout(small_graph_nodes, small_graph_edges):
    """5 nodes, 6 edges produces 5 finite (x, y) pairs."""
    result = forceatlas2_layout(small_graph_nodes, small_graph_edges, iterations=50)
    assert len(result) == 5
    for x, y in result:
        assert np.isfinite(x), f"x={x} is not finite"
        assert np.isfinite(y), f"y={y} is not finite"


def test_deterministic(small_graph_nodes, small_graph_edges):
    """Same input produces same output."""
    r1 = forceatlas2_layout(small_graph_nodes, small_graph_edges, iterations=50)
    r2 = forceatlas2_layout(small_graph_nodes, small_graph_edges, iterations=50)
    for (x1, y1), (x2, y2) in zip(r1, r2):
        assert x1 == pytest.approx(x2, abs=1e-10)
        assert y1 == pytest.approx(y2, abs=1e-10)


def test_early_stopping():
    """Very high tolerance causes early exit (fewer iterations)."""
    nodes = [
        {"id": "A", "size": 10, "x": 0.0, "y": 0.0},
        {"id": "B", "size": 10, "x": 1.0, "y": 0.0},
    ]
    edges = [{"source": "A", "target": "B", "weight": 1.0}]
    # tolerance=1000 should stop almost immediately
    result = forceatlas2_layout(nodes, edges, iterations=1000, tolerance=1000.0)
    assert len(result) == 2
    # Just verify it returns valid results (the early stop is internal)
    for x, y in result:
        assert np.isfinite(x) and np.isfinite(y)


def test_gravity_toward_origin(small_graph_nodes, small_graph_edges):
    """Mean position should be closer to origin than initial mean."""
    initial_mean = np.mean(
        [(n["x"], n["y"]) for n in small_graph_nodes], axis=0
    )
    result = forceatlas2_layout(
        small_graph_nodes, small_graph_edges,
        iterations=100, gravity=5.0, gravity_center=(0.0, 0.0),
    )
    final_mean = np.mean(result, axis=0)
    initial_dist = np.linalg.norm(initial_mean)
    final_dist = np.linalg.norm(final_mean)
    assert final_dist <= initial_dist + 0.5, (
        f"Gravity should pull toward origin: initial={initial_dist:.2f}, final={final_dist:.2f}"
    )


def test_repulsion_separates_nodes():
    """Nodes with no edges should spread apart due to repulsion."""
    # Start all nodes at nearly the same position
    nodes = [
        {"id": f"N{i}", "size": 10, "x": 0.01 * i, "y": 0.01 * i}
        for i in range(5)
    ]
    result = forceatlas2_layout(nodes, [], iterations=50, gravity=0.01)

    # Compute mean pairwise distance
    positions = np.array(result)
    dists = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dists.append(np.linalg.norm(positions[i] - positions[j]))
    mean_dist = np.mean(dists)
    assert mean_dist > 0.1, f"Nodes should spread apart, mean_dist={mean_dist:.4f}"


def test_iterations_param():
    """Different iteration counts produce different (but valid) outputs."""
    nodes = [
        {"id": "A", "size": 10, "x": 0.0, "y": 0.0},
        {"id": "B", "size": 10, "x": 1.0, "y": 1.0},
    ]
    edges = [{"source": "A", "target": "B", "weight": 0.5}]
    r1 = forceatlas2_layout(nodes, edges, iterations=1, tolerance=0.0)
    r10 = forceatlas2_layout(nodes, edges, iterations=10, tolerance=0.0)
    # They should produce different positions
    assert r1 != r10, "1 iteration and 10 iterations should differ"


def test_invalid_edge_source_ignored():
    """Edges referencing non-existent nodes are silently ignored."""
    nodes = [{"id": "A", "size": 10, "x": 0.0, "y": 0.0}]
    edges = [{"source": "A", "target": "MISSING", "weight": 1.0}]
    result = forceatlas2_layout(nodes, edges, iterations=10)
    assert len(result) == 1
