"""Predictive UI conventions ("logo top-left -> nav links right of it"). Reads `priors.json`.

Step 1: stub. Step 6: anchor + prediction engine that emits `inferred=True` elements.
"""

from __future__ import annotations

from .schema import Element


def apply(elements: list[Element]) -> list[Element]:
    raise NotImplementedError("Step 6 - priors.apply not yet implemented")
