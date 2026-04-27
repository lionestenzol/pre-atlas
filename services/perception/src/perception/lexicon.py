"""Phrase-to-ElementType classifier. Reads `lexicon.json`.

Step 1: stub. Step 5: full matcher with `lexicon` evidence stream.
"""

from __future__ import annotations

from .schema import Element, TextContent


def apply(elements: list[Element], text_elements: list[TextContent]) -> list[Element]:
    raise NotImplementedError("Step 5 - lexicon.apply not yet implemented")
