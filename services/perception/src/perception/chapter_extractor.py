"""Derive narrative chapters from typography hierarchy + containment + patterns.

Step 1: stub. Step 9: real heuristic. Returns `ChapterResult` so spec §4's
`chaptered.elements, chaptered.chapters` access pattern works.
"""

from __future__ import annotations

from .schema import ChapterResult, Element


def extract(elements: list[Element]) -> ChapterResult:
    raise NotImplementedError(
        "Step 9 - chapter_extractor.extract not yet implemented"
    )
