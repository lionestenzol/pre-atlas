"""Constants for the perception pipeline. No magic numbers live in modules."""

from __future__ import annotations

from pathlib import Path

from .schema import EvidenceStream

VERSION = "0.1.0"

# Calibrator thresholds (Step 4).
AXIS_TOLERANCE_PCT = 2.0
SIGNATURE_ROUND_PCT = 5.0

# Reconciler weights (Step 8 - placeholder values).
EVIDENCE_WEIGHTS: dict[EvidenceStream, float] = {
    "scanner_geometry": 1.0,
    "text_extractor": 0.9,
    "lexicon": 0.85,
    "calibrator_repetition": 0.7,
    "prior_prediction": 0.6,
    "pattern_match": 0.75,
    "user_correction": 1.0,
}

# Paths anchored to the installed package, not cwd.
_PKG_ROOT: Path = Path(__file__).resolve().parent
DEBUG_DIR: Path = _PKG_ROOT / "debug"
CORRECTIONS_PATH: Path = _PKG_ROOT / "corrections.jsonl"
LEXICON_PATH: Path = _PKG_ROOT / "lexicon.json"
PRIORS_PATH: Path = _PKG_ROOT / "priors.json"
