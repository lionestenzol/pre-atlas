"""Input/output contracts for the triangulation pipeline. Frozen on input, mutable on output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Verdict = Literal["confirmed", "flagged", "rejected"]


@dataclass(frozen=True)
class ElementInput:
    id: str
    label: str
    bbox: tuple[float, float, float, float]   # (x, y, w, h) in page pixels
    parent_id: Optional[str]
    screenshot_path: str
    page_id: str

    @classmethod
    def from_dict(cls, d: dict) -> "ElementInput":
        bbox = d["bbox"]
        if isinstance(bbox, list):
            bbox = tuple(bbox)
        if len(bbox) != 4:
            raise ValueError(f"bbox must have 4 elements, got {len(bbox)}")
        return cls(
            id=d["id"],
            label=d["label"],
            bbox=bbox,
            parent_id=d.get("parent_id"),
            screenshot_path=d["screenshot_path"],
            page_id=d["page_id"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "bbox": list(self.bbox),
            "parent_id": self.parent_id,
            "screenshot_path": self.screenshot_path,
            "page_id": self.page_id,
        }


@dataclass
class SpatialSignal:
    """Spatial geometry score. `score=None` when element has no aligned siblings."""

    score: Optional[float]
    alignment_groups: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "alignment_groups": [list(g) for g in self.alignment_groups],
            "notes": list(self.notes),
        }


@dataclass
class VisualSignal:
    """Visual similarity score. `score=None` on cold start (empty library)."""

    score: Optional[float] = None
    nearest_label: Optional[str] = None
    distance: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "nearest_label": self.nearest_label,
            "distance": self.distance,
        }


@dataclass
class VerifyResult:
    id: str
    label: str
    confidence: float
    signals: dict[str, Any]                     # {"spatial": SpatialSignal, "visual": VisualSignal}
    flags: list[str] = field(default_factory=list)
    verdict: Verdict = "flagged"
    behavioral_score: Optional[float] = None    # stretch hook per brief; never populated in Phase A-C

    def to_dict(self) -> dict:
        signals_serialized: dict[str, Any] = {}
        for key, sig in self.signals.items():
            if hasattr(sig, "to_dict"):
                signals_serialized[key] = sig.to_dict()
            else:
                signals_serialized[key] = sig
        return {
            "id": self.id,
            "label": self.label,
            "confidence": self.confidence,
            "signals": signals_serialized,
            "flags": list(self.flags),
            "verdict": self.verdict,
            "behavioral_score": self.behavioral_score,
        }
