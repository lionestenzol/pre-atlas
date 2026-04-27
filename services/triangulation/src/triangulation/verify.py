"""Top-level `verify(elements)` entry point. Composes spatial + visual + consensus."""

from __future__ import annotations

from typing import Optional

from . import consensus, spatial, visual
from .schema import VerifyResult


def verify(
    elements: list[dict],
    embedder: Optional[visual.Embedder] = None,
    library: Optional[visual.ReferenceLibrary] = None,
) -> list[VerifyResult]:
    """Verify a list of elements via spatial + visual triangulation.

    Cold-start (`library is None`, or empty library) skips the visual signal
    cleanly. Embedder is only invoked if both `embedder` and a populated
    `library` are provided.
    """
    if library is None:
        library = visual.ReferenceLibrary()

    results: list[VerifyResult] = []
    for el in elements:
        spatial_result = spatial.score_element(el, elements)

        if embedder is None or not library.stats():
            visual_result = {"score": None, "nearest_label": None, "distance": None}
        else:
            visual_result = visual.score_element(el, embedder, library)

        results.append(consensus.aggregate(el, spatial_result, visual_result))
    return results
