"""Perception system - public surface."""

from perception.config import VERSION
from perception.pipeline import perceive
from perception.schema import (
    Chapter,
    ChapterResult,
    Element,
    ElementType,
    EvidenceStream,
    PageGraph,
    Signature,
    TextContent,
)

__all__ = [
    "Chapter",
    "ChapterResult",
    "Element",
    "ElementType",
    "EvidenceStream",
    "PageGraph",
    "Signature",
    "TextContent",
    "VERSION",
    "perceive",
]
