"""Visual signal via SigLIP-2 embeddings.

Phase A: `Embedder.embed` raises `NotImplementedError` (model not loaded yet).
`ReferenceLibrary` is fully implemented in pure numpy. `score_element` handles
the cold-start path (empty library, or no entries for this label) without
calling the embedder.

Phase B will load `google/siglip2-base-patch16-256` lazily on first `.embed()`
call to avoid paying the ~400MB download + import cost at module-import time.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .config import SIGLIP_MODEL_NAME


class Embedder:
    """Loads the SigLIP-2 model and exposes `.embed(image_path) -> np.ndarray`."""

    def __init__(self, model_name: str = SIGLIP_MODEL_NAME) -> None:
        self.model_name = model_name
        # Phase B: load model lazily on first .embed() call.

    def embed(self, image_path: str) -> np.ndarray:
        raise NotImplementedError(
            "Phase B - visual.Embedder.embed not yet implemented. "
            "Install with `pip install -e \".[visual]\"` and provide a SigLIP-2-backed implementation."
        )


class ReferenceLibrary:
    """In-memory `{label: [embedding, ...]}` store with persistence."""

    def __init__(self) -> None:
        self._labels: dict[str, list[np.ndarray]] = {}

    def add(self, label: str, embedding: np.ndarray) -> None:
        self._labels.setdefault(label, []).append(np.asarray(embedding, dtype=np.float32))

    def has(self, label: str) -> bool:
        return label in self._labels and len(self._labels[label]) > 0

    def centroid(self, label: str) -> Optional[np.ndarray]:
        if not self.has(label):
            return None
        return np.mean(self._labels[label], axis=0)

    def nearest_label(self, embedding: np.ndarray) -> Optional[tuple[str, float]]:
        """Return `(label, cosine_distance)` for the closest centroid, or None on empty library."""
        if not self._labels:
            return None
        emb = np.asarray(embedding, dtype=np.float32)
        emb_norm = float(np.linalg.norm(emb))
        if emb_norm < 1e-9:
            return None

        best_label: Optional[str] = None
        best_dist = float("inf")
        for label in self._labels:
            cent = self.centroid(label)
            if cent is None:
                continue
            cent_norm = float(np.linalg.norm(cent))
            if cent_norm < 1e-9:
                continue
            cosine_sim = float(np.dot(cent, emb)) / (cent_norm * emb_norm)
            dist = 1.0 - cosine_sim
            if dist < best_dist:
                best_dist = dist
                best_label = label
        if best_label is None:
            return None
        return (best_label, best_dist)

    def stats(self) -> dict[str, int]:
        return {label: len(embs) for label, embs in self._labels.items()}

    def persist(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._labels, f)

    @classmethod
    def load(cls, path: Path) -> "ReferenceLibrary":
        lib = cls()
        with open(path, "rb") as f:
            lib._labels = pickle.load(f)
        return lib


def score_element(
    element: dict,
    embedder: Embedder,
    library: ReferenceLibrary,
) -> dict[str, Any]:
    """Score visual similarity of `element` to its DOM-claimed label.

    Cold-start path (empty library or no entries for the element's label) returns
    `{score: None, nearest_label: None, distance: None}` without invoking the
    embedder. Per brief: do not penalize cold start.
    """
    if not library.stats():
        return {"score": None, "nearest_label": None, "distance": None}

    if not library.has(element["label"]):
        return {"score": None, "nearest_label": None, "distance": None}

    emb = embedder.embed(element["screenshot_path"])
    result = library.nearest_label(emb)
    if result is None:
        return {"score": None, "nearest_label": None, "distance": None}

    nearest, dist = result
    if nearest == element["label"]:
        score = max(0.0, 1.0 - dist)
    else:
        # Visual disagrees with DOM. Score reflects the disagreement.
        score = max(0.0, 0.3 - dist)

    return {"score": score, "nearest_label": nearest, "distance": dist}
