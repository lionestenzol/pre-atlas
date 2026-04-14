"""
atlas_layout.py -- ForceAtlas2-style force-directed layout (pure NumPy).

Computes positions for graph nodes using repulsion, attraction, and gravity forces.
Extracted from build_cognitive_atlas.py for independent testing and improvement.

Improvements over original:
- Gravity pulls toward (0,0) instead of centroid drift
- Symmetric attraction forces (both nodes receive proportional force)
- Early stopping when maximum displacement falls below threshold
- All parameters configurable as keyword arguments
"""
import numpy as np


def forceatlas2_layout(nodes, edges, *, iterations=200, gravity=1.0,
                       scaling=10.0, tolerance=0.01,
                       gravity_center=(0.0, 0.0)):
    """
    Pure-numpy ForceAtlas2-style spring layout.

    Args:
        nodes: list[dict] with keys 'id', 'x', 'y', 'size'
        edges: list[dict] with keys 'source', 'target', 'weight'
        iterations: max iterations (default 200)
        gravity: gravity constant (default 1.0)
        scaling: repulsion scaling (default 10.0)
        tolerance: early stopping threshold on max displacement (default 0.01)
        gravity_center: (x, y) gravity anchor (default (0.0, 0.0))

    Returns:
        list[tuple[float, float]] -- (x, y) positions for each node
    """
    n = len(nodes)
    if n == 0:
        return []

    node_idx = {node["id"]: i for i, node in enumerate(nodes)}

    # Initialize from UMAP centroids (or whatever x/y the nodes carry)
    pos = np.array([[node["x"], node["y"]] for node in nodes], dtype=np.float64)

    # Node masses (log-scaled sizes)
    masses = np.array([max(1.0, np.log1p(node["size"])) for node in nodes])

    # Parse edges into index triples
    edge_list = []
    for e in edges:
        si = node_idx.get(e["source"])
        ti = node_idx.get(e["target"])
        if si is not None and ti is not None:
            edge_list.append((si, ti, e["weight"]))

    center = np.array(gravity_center, dtype=np.float64)

    for iteration in range(iterations):
        forces = np.zeros_like(pos)

        # Repulsion (all pairs) -- vectorized
        for i in range(n):
            diff = pos[i] - pos[i + 1:]  # (n-i-1, 2)
            dist = np.linalg.norm(diff, axis=1)
            dist = np.maximum(dist, 0.01)
            rep = scaling * masses[i] * masses[i + 1:] / (dist * dist)
            direction = diff / dist[:, np.newaxis]
            f = direction * rep[:, np.newaxis]
            forces[i] += f.sum(axis=0)
            forces[i + 1:] -= f

        # Attraction (edges) -- symmetric force sharing
        for si, ti, w in edge_list:
            diff = pos[ti] - pos[si]
            dist = max(np.linalg.norm(diff), 0.01)
            attraction = w * dist
            direction = diff / dist
            total_mass = masses[si] + masses[ti]
            forces[si] += direction * attraction * masses[ti] / total_mass
            forces[ti] -= direction * attraction * masses[si] / total_mass

        # Gravity toward fixed center (default origin)
        for i in range(n):
            diff = center - pos[i]
            dist = max(np.linalg.norm(diff), 0.01)
            forces[i] += gravity * masses[i] * diff / dist

        # Apply with decreasing step size
        step = 1.0 / (1 + iteration * 0.05)
        displacement = forces * step / masses[:, np.newaxis]
        pos += displacement

        # Early stopping
        max_disp = np.max(np.linalg.norm(displacement, axis=1))
        if max_disp < tolerance:
            break

    return [(float(pos[i, 0]), float(pos[i, 1])) for i in range(n)]
