"""
atlas_graph.py -- Build cluster-level force-directed graph for the Cognitive Atlas.

Constructs nodes from cluster aggregations, computes edges via two strategies
(conversation overlap + semantic cosine similarity), merges and prunes to top-K,
then runs ForceAtlas2 layout.
"""
import numpy as np
from collections import Counter
from sklearn.metrics.pairwise import cosine_similarity
from atlas_layout import forceatlas2_layout

# Configurable thresholds (defaults match current production values)
DEFAULT_OVERLAP_MIN = 0.15
DEFAULT_SIM_MIN = 0.4
DEFAULT_MAX_EDGES_PER_NODE = 5
DEFAULT_FA2_ITERATIONS = 200


def build_graph_data(data, labels, umap_coords, matrix, leverage_data,
                     *, overlap_min=DEFAULT_OVERLAP_MIN,
                     sim_min=DEFAULT_SIM_MIN,
                     max_edges_per_node=DEFAULT_MAX_EDGES_PER_NODE,
                     fa2_iterations=DEFAULT_FA2_ITERATIONS,
                     fa2_kwargs=None):
    """
    Build force-directed graph: cluster nodes + weighted edges.

    Args:
        data: dict from load_message_data()
        labels: np.ndarray of cluster labels
        umap_coords: np.ndarray (N, 2) -- UMAP coordinates per message
        matrix: np.ndarray (N, D) -- embedding vectors per message
        leverage_data: dict or None (from leverage_map.json)
        overlap_min: minimum conversation overlap for edge (default 0.15)
        sim_min: minimum cosine similarity for edge (default 0.4)
        max_edges_per_node: top-K edge pruning (default 5)
        fa2_iterations: ForceAtlas2 iterations (default 200)
        fa2_kwargs: optional dict of additional FA2 params (tolerance, gravity, etc.)

    Returns:
        dict with keys:
            nodes: list[dict] -- node attributes including FA2 positions (fx, fy)
            edges: list[dict] -- edge attributes including weight and type
    """
    unique_labels = sorted(set(labels))
    unique_labels = [l for l in unique_labels if l != -1]

    # ── Cluster-level aggregations ──
    cluster_info = {}
    for cl in unique_labels:
        mask = labels == cl
        indices = np.where(mask)[0]
        cx = float(np.mean(umap_coords[indices, 0]))
        cy = float(np.mean(umap_coords[indices, 1]))
        size = int(mask.sum())
        convos = set(data["convo_ids"][i] for i in indices)
        cluster_info[cl] = {
            "cx": cx, "cy": cy, "size": size,
            "indices": indices, "convos": convos,
        }

    # ── Leverage lookup ──
    lev_lookup = {}
    if leverage_data:
        for cl_d in leverage_data.get("clusters", []):
            lev_lookup[cl_d["cluster_id"]] = {
                "normalized_leverage": cl_d["normalized_leverage"],
                "asset_vector": cl_d["asset_vector"],
                "revenue_tag": cl_d.get("revenue_tag", ""),
                "conversations": cl_d.get("conversations", 0),
            }

    # ── Build nodes ──
    nodes = []
    for cl in unique_labels:
        info = cluster_info[cl]
        lev = lev_lookup.get(cl)
        node = {
            "id": f"C{cl}", "cluster_id": int(cl),
            "size": info["size"],
            "x": round(info["cx"], 4), "y": round(info["cy"], 4),
            "has_leverage": lev is not None,
        }
        if lev:
            node["normalized_leverage"] = lev["normalized_leverage"]
            node["asset_vector"] = lev["asset_vector"]
            node["revenue_tag"] = lev.get("revenue_tag", "")
            node["conversations"] = lev.get("conversations", 0)
        nodes.append(node)

    # ── Edge Strategy 1: Conversation Overlap ──
    cl_list = list(unique_labels)
    n_cl = len(cl_list)
    overlap_weights = {}
    for i in range(n_cl):
        for j in range(i + 1, n_cl):
            ci, cj = cl_list[i], cl_list[j]
            shared = len(cluster_info[ci]["convos"] & cluster_info[cj]["convos"])
            if shared > 0:
                min_c = min(len(cluster_info[ci]["convos"]), len(cluster_info[cj]["convos"]))
                w = shared / min_c if min_c > 0 else 0
                if w >= overlap_min:
                    overlap_weights[(ci, cj)] = round(w, 4)

    # ── Edge Strategy 2: Centroid Cosine Similarity (384-dim) ──
    centroids = np.zeros((n_cl, matrix.shape[1]))
    for idx, cl in enumerate(cl_list):
        centroids[idx] = matrix[cluster_info[cl]["indices"]].mean(axis=0)

    sim_matrix = cosine_similarity(centroids)
    semantic_weights = {}
    for i in range(n_cl):
        for j in range(i + 1, n_cl):
            sim = float(sim_matrix[i, j])
            if sim >= sim_min:
                semantic_weights[(cl_list[i], cl_list[j])] = round(sim, 4)

    # ── Merge: composite weight, top-K per node ──
    all_pairs = set(overlap_weights.keys()) | set(semantic_weights.keys())
    raw_edges = []
    for pair in all_pairs:
        ow = overlap_weights.get(pair, 0)
        sw = semantic_weights.get(pair, 0)
        composite = round(0.5 * ow + 0.5 * sw, 4) if ow > 0 and sw > 0 else max(ow, sw)
        etype = "both" if ow > 0 and sw > 0 else ("overlap" if ow > 0 else "semantic")
        raw_edges.append({
            "source": f"C{pair[0]}", "target": f"C{pair[1]}",
            "weight": composite, "type": etype,
        })

    raw_edges.sort(key=lambda e: -e["weight"])
    node_edge_count = Counter()
    edges = []
    for e in raw_edges:
        s, t = e["source"], e["target"]
        if node_edge_count[s] < max_edges_per_node and node_edge_count[t] < max_edges_per_node:
            edges.append(e)
            node_edge_count[s] += 1
            node_edge_count[t] += 1

    # ── ForceAtlas2 layout ──
    kwargs = {"iterations": fa2_iterations}
    if fa2_kwargs:
        kwargs.update(fa2_kwargs)
    positions = forceatlas2_layout(nodes, edges, **kwargs)
    for node, (fx, fy) in zip(nodes, positions):
        node["fx"] = round(fx, 4)
        node["fy"] = round(fy, 4)

    print(f"  Graph: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges}
