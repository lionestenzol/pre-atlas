"""Tests for atlas_projection.py -- UMAP and HDBSCAN wrappers."""
import numpy as np
import pytest
from atlas_projection import compute_umap, compute_hdbscan, UMAP_DEFAULTS, HDBSCAN_DEFAULTS


def test_umap_defaults_documented():
    """Verify default constants match expected production values."""
    assert UMAP_DEFAULTS["n_neighbors"] == 30
    assert UMAP_DEFAULTS["min_dist"] == 0.05
    assert UMAP_DEFAULTS["metric"] == "cosine"


def test_hdbscan_defaults_documented():
    """Verify default constants match expected production values."""
    assert HDBSCAN_DEFAULTS["min_cluster_size"] == 50
    assert HDBSCAN_DEFAULTS["min_samples"] == 10


@pytest.mark.slow
def test_compute_umap_output_shape(small_embeddings):
    """200 x 384 input -> 200 x 2 output."""
    coords = compute_umap(small_embeddings, verbose=False)
    assert coords.shape == (200, 2)
    assert np.all(np.isfinite(coords))


@pytest.mark.slow
def test_compute_umap_deterministic(small_embeddings):
    """Same random_state produces same output."""
    c1 = compute_umap(small_embeddings, random_state=42, verbose=False)
    c2 = compute_umap(small_embeddings, random_state=42, verbose=False)
    np.testing.assert_array_almost_equal(c1, c2)


@pytest.mark.slow
def test_compute_umap_custom_params(small_embeddings):
    """Custom params still produce valid output."""
    coords = compute_umap(
        small_embeddings,
        n_neighbors=15, min_dist=0.1, verbose=False,
    )
    assert coords.shape == (200, 2)


@pytest.mark.slow
def test_compute_hdbscan_returns_labels(small_umap_coords):
    """Output is 1D array of correct length with integer labels."""
    labels = compute_hdbscan(small_umap_coords)
    assert labels.shape == (200,)
    assert labels.dtype in (np.intp, np.int32, np.int64)
    # Should have at least some noise (-1) or clusters
    unique = set(labels)
    assert len(unique) >= 1


@pytest.mark.slow
def test_compute_hdbscan_custom_params(small_umap_coords):
    """Custom params produce valid output."""
    labels = compute_hdbscan(
        small_umap_coords,
        min_cluster_size=20, min_samples=5,
    )
    assert labels.shape == (200,)
