"""Constants. Tolerances are placeholders per brief - DO NOT TUNE until Phase D."""

from __future__ import annotations

from pathlib import Path

VERSION = "0.1.0"

# Spatial tolerances (per brief, do not tune)
ALIGNMENT_TOLERANCE_PX: int = 4
LABEL_CONSISTENCY_THRESHOLD: float = 0.85

# Spatial scoring threshold below which an element is flagged as a spatial outlier.
SPATIAL_OUTLIER_THRESHOLD: float = 0.5

# Consensus weights (per brief, do not tune)
SIGNAL_WEIGHTS: dict[str, float] = {
    "dom": 0.30,
    "spatial": 0.35,
    "visual": 0.35,
}

# Visual model
SIGLIP_MODEL_NAME: str = "google/siglip2-base-patch16-256"

# Persistence
_PKG_ROOT: Path = Path(__file__).resolve().parent
LIBRARY_PERSIST_PATH: Path = _PKG_ROOT / "library.pkl"

# API
API_DEFAULT_PORT: int = 3010
