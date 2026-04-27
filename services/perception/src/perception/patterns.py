"""Structural archetype recognizer (card_grid, hero_stack, pricing_table, ...).

Step 1: stub. Step 7: pattern functions that return matched regions with confidence.
"""

from __future__ import annotations

from .schema import Element


def match(elements: list[Element]) -> list[Element]:
    raise NotImplementedError("Step 7 - patterns.match not yet implemented")
