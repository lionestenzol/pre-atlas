"""
atlas_projection.py -- UMAP dimensionality reduction and HDBSCAN clustering.

Thin wrappers with configurable parameters. Heavy dependencies (umap-learn,
hdbscan) are lazy-imported so other modules can be tested without them.
"""
import numpy as np

# Default parameters (matching current production values)
UMAP_DEFAULTS = {
    "n_neighbors": 30,
    "min_dist": 0.05,
    "metric": "cosine",
    "n_components": 2,
    "random_state": 42,
}

HDBSCAN_DEFAULTS = {
    "min_cluster_size": 50,
    "min_samples": 10,
    "metric": "euclidean",
    "cluster_selection_method": "eom",
}


def compute_umap(matrix, *, n_neighbors=30, min_dist=0.05,
                 metric="cosine", random_state=42, verbose=True):
    """
    Compute UMAP projection from high-dim embeddings to 2D.

    Args:
        matrix: np.ndarray of shape (N, D)
        n_neighbors: UMAP neighbor count (default 30)
        min_dist: UMAP minimum distance (default 0.05)
        metric: distance metric (default "cosine")
        random_state: for reproducibility (default 42)
        verbose: print UMAP progress (default True)

    Returns:
        np.ndarray of shape (N, 2) -- UMAP coordinates
    """
    import umap  # lazy import (heavy dependency)
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=2,
        metric=metric,
        random_state=random_state,
        verbose=verbose,
    )
    return reducer.fit_transform(matrix)


def compute_hdbscan(coords_2d, *, min_cluster_size=50, min_samples=10,
                     metric="euclidean", cluster_selection_method="eom"):
    """
    Compute HDBSCAN clusters on 2D coordinates.

    Args:
        coords_2d: np.ndarray of shape (N, 2)
        min_cluster_size: minimum cluster size (default 50)
        min_samples: minimum samples for core points (default 10)
        metric: distance metric (default "euclidean")
        cluster_selection_method: "eom" or "leaf" (default "eom")

    Returns:
        np.ndarray of int labels, shape (N,). -1 = noise.
    """
    import hdbscan  # lazy import (heavy dependency)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric=metric,
        cluster_selection_method=cluster_selection_method,
    )
    return clusterer.fit_predict(coords_2d)
