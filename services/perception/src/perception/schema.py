"""Canonical perception schema. Frozen per spec §2 - no extra fields without approval.

Every pipeline module reads and writes the dataclasses in this file. IDs are stable
strings; modules enrich the same `Element` instance rather than minting new ones.
All percentages are 0-100, not 0-1. Confidence 0.0 = no evidence yet; 1.0 = all
evidence streams agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class ElementType(str, Enum):
    NAV = "nav"
    HERO = "hero"
    CTA = "cta"
    FEATURE = "feature"
    PRICING = "pricing"
    FORM = "form"
    FOOTER = "footer"
    NAV_LINK = "nav_link"
    AUTH_CTA = "auth_cta"
    LOGO = "logo"
    HEADING = "heading"
    SUBHEAD = "subhead"
    BODY = "body"
    IMAGE = "image"
    ICON = "icon"
    UNKNOWN = "unknown"


EvidenceStream = Literal[
    "scanner_geometry",
    "text_extractor",
    "lexicon",
    "calibrator_repetition",
    "prior_prediction",
    "pattern_match",
    "user_correction",
]


@dataclass
class TextContent:
    content: str
    font_size: float
    font_weight: int
    color: Optional[str] = None
    is_aria: bool = False
    is_alt: bool = False


@dataclass
class Signature:
    type: str
    rounded_w: int
    rounded_h: int
    child_count: int
    child_types: tuple[str, ...] = field(default_factory=tuple)

    def __hash__(self) -> int:
        return hash(
            (
                self.type,
                self.rounded_w,
                self.rounded_h,
                self.child_count,
                self.child_types,
            )
        )


@dataclass
class Element:
    # Identity
    id: str
    type: ElementType
    label: str

    # Geometry (percentages of viewport, 0-100)
    x: float
    y: float
    w: float
    h: float

    # Calibration (populated by calibrator)
    axes: list[str] = field(default_factory=list)
    signature: Optional[Signature] = None
    repetition_group: Optional[str] = None

    # Text (populated by text extractor)
    text: Optional[TextContent] = None

    # Confidence + provenance (populated by reconciler)
    confidence: float = 0.0
    evidence: list[EvidenceStream] = field(default_factory=list)
    inferred: bool = False
    conflicts: list[str] = field(default_factory=list)

    # Hierarchy
    parent_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)

    # Pattern + chapter
    pattern_match: Optional[str] = None
    chapter: Optional[int] = None

    # Metadata
    dom_tag: Optional[str] = None
    scanner_id: Optional[str] = None


@dataclass
class Chapter:
    id: int
    title: str
    desc: str
    element_ids: list[str]


@dataclass
class PageGraph:
    url: str
    elements: list[Element]
    chapters: list[Chapter]
    scan_timestamp: str
    pipeline_version: str


@dataclass
class ChapterResult:
    """Return value of `chapter_extractor.extract`. Spec §4 accesses
    `chaptered.elements` and `chaptered.chapters`, so the extractor must return
    both. Small additive support type, not a schema change.
    """

    elements: list[Element]
    chapters: list[Chapter]
