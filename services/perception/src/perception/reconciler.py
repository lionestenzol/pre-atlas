"""The brain. Fuses all evidence streams into confidence-scored, provenance-tagged Elements.

Step 1: stub. Step 2: pass-through that sets `confidence=0.5,
evidence=["scanner_geometry"]`. Step 8: full weighted-vote fusion with conflict
logging using `EVIDENCE_WEIGHTS` from config.
"""

from __future__ import annotations

from .schema import Element, TextContent


def fuse(
    geometric: list[Element],
    text: list[TextContent],
    debug: bool = False,
) -> list[Element]:
    raise NotImplementedError("Step 8 - reconciler.fuse not yet implemented")
