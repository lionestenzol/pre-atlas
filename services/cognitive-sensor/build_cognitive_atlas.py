"""
build_cognitive_atlas.py -- Phase 2 Cognitive Atlas

Reads message-level embeddings from results.db, computes UMAP projection,
HDBSCAN clusters, and generates interactive HTML atlas with toggle layers.

Layers: Cluster | Role | Time | Conversation
Uses scattergl (WebGL) for 84K+ point rendering.

Requirements: umap-learn, hdbscan (pip install -r requirements.txt)

Usage:
    python build_cognitive_atlas.py

Modules:
    atlas_data.py        -- DB loading
    atlas_projection.py  -- UMAP + HDBSCAN
    atlas_layers.py      -- Layer building + cluster summary
    atlas_layout.py      -- ForceAtlas2 physics simulation
    atlas_graph.py       -- Graph node/edge construction
    atlas_render.py      -- HTML payload + template fill
    atlas_template.html  -- HTML template
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from atlas_data import load_message_data
from atlas_projection import compute_umap, compute_hdbscan
from atlas_layers import build_layers, build_cluster_summary
from atlas_render import build_html

BASE = Path(__file__).parent.resolve()


def write_cluster_export(data: dict, labels: np.ndarray,
                         cluster_summary: list, matrix: np.ndarray) -> None:
    """Write atlas_clusters.json for downstream consumers (Genesis).

    Exports per-conversation cluster assignments and centroids derived from
    the HDBSCAN labels computed on message-level embeddings.
    """
    from collections import defaultdict

    # Group messages by convo_id, collect their cluster labels
    convo_labels: dict[str, list[int]] = defaultdict(list)
    convo_vecs: dict[str, list[np.ndarray]] = defaultdict(list)

    for i, cid in enumerate(data["convo_ids"]):
        convo_labels[cid].append(int(labels[i]))
        convo_vecs[cid].append(matrix[i])

    # Per-conversation: majority-vote cluster label + centroid
    convo_cluster_assignments: dict[str, int] = {}
    convo_centroids: dict[str, list[float]] = {}

    for cid in convo_labels:
        # Majority vote (exclude noise=-1 if possible)
        lbl_list = convo_labels[cid]
        non_noise = [l for l in lbl_list if l != -1]
        if non_noise:
            convo_cluster_assignments[cid] = max(set(non_noise), key=non_noise.count)
        else:
            convo_cluster_assignments[cid] = -1

        # Centroid of conversation messages
        vecs = np.array(convo_vecs[cid])
        centroid = vecs.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        convo_centroids[cid] = centroid.tolist()

    # Per-cluster centroids (mean of conversation centroids in that cluster)
    cluster_ids = sorted(set(convo_cluster_assignments.values()) - {-1})
    cluster_centroids: dict[str, list[float]] = {}
    for cid_cluster in cluster_ids:
        members = [c for c, l in convo_cluster_assignments.items() if l == cid_cluster]
        if members:
            vecs = np.array([convo_centroids[m] for m in members])
            centroid = vecs.mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            cluster_centroids[str(cid_cluster)] = centroid.tolist()

    export = {
        "generated_at": datetime.now().isoformat(),
        "total_messages": len(data["convo_ids"]),
        "total_conversations": len(convo_labels),
        "cluster_count": len(cluster_ids),
        "convo_cluster_assignments": convo_cluster_assignments,
        "convo_centroids": convo_centroids,
        "cluster_centroids": cluster_centroids,
        "cluster_summary": cluster_summary,
    }

    out_path = BASE / "atlas_clusters.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, default=str)
    print(f"  Wrote {out_path.name} ({len(cluster_ids)} clusters, "
          f"{len(convo_labels)} conversations)")


def main():
    t0 = datetime.now()

    print("Loading message embeddings from results.db...")
    data = load_message_data()
    n = len(data["convo_ids"])
    print(f"  Loaded {n:,} messages ({data['matrix'].shape[1]}D)")
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"  [{elapsed:.1f}s elapsed]")

    print("Computing UMAP projection (384D -> 2D)...")
    print(f"  n_neighbors=30, min_dist=0.05, metric=cosine")
    umap_coords = compute_umap(data["matrix"])
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"  [{elapsed:.1f}s elapsed]")

    print("Computing HDBSCAN clusters...")
    print(f"  min_cluster_size=50, min_samples=10")
    labels = compute_hdbscan(umap_coords)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    noise = int(np.sum(labels == -1))
    print(f"  Clusters: {n_clusters}")
    print(f"  Noise: {noise} ({100*noise/n:.1f}%)")
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"  [{elapsed:.1f}s elapsed]")

    print("Building layer data...")
    layers = build_layers(data, labels)

    print("Building cluster summary...")
    cluster_summary = build_cluster_summary(data, labels)
    for cs in cluster_summary[:5]:
        top = cs["top_titles"][0]["title"] if cs["top_titles"] else "?"
        print(f"  Cluster {cs['id']}: {cs['count']} msgs, {cs['user_pct']}% user, top: {top}")

    print("Exporting cluster data for Genesis...")
    write_cluster_export(data, labels, cluster_summary, data["matrix"])

    print("Building HTML...")
    build_html(data, umap_coords, labels, layers, cluster_summary, data["matrix"])

    total = (datetime.now() - t0).total_seconds()
    print(f"\nDone in {total:.1f}s. Open cognitive_atlas.html in a browser.")


if __name__ == "__main__":
    main()
