"""Triangulation Labeler - public surface."""

from .config import VERSION
from .schema import (
    ElementInput,
    SpatialSignal,
    VerifyResult,
    Verdict,
    VisualSignal,
)
from .visual import Embedder, ReferenceLibrary
from .verify import verify

__all__ = [
    "Embedder",
    "ElementInput",
    "ReferenceLibrary",
    "SpatialSignal",
    "VERSION",
    "Verdict",
    "VerifyResult",
    "VisualSignal",
    "verify",
]
