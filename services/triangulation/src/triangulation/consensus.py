"""Consensus aggregator. Quorum vote across DOM, spatial, and visual signals.

Verdict logic per brief:
  - Both available signals agree with DOM -> confirmed
  - One signal disagrees -> flagged
  - Both signals disagree (and visual has a non-empty alternate) -> rejected
  - Cold-start (signal returns score=None) does not count as disagreement.
"""

from __future__ import annotations

from typing import Any

from .config import SIGNAL_WEIGHTS, SPATIAL_OUTLIER_THRESHOLD
from .schema import SpatialSignal, Verdict, VerifyResult, VisualSignal


def aggregate(
    element: dict,
    spatial: dict[str, Any] | SpatialSignal,
    visual: dict[str, Any] | VisualSignal,
) -> VerifyResult:
    spatial_dict = spatial.to_dict() if isinstance(spatial, SpatialSignal) else spatial
    visual_dict = visual.to_dict() if isinstance(visual, VisualSignal) else visual

    spatial_score = spatial_dict.get("score")
    visual_score = visual_dict.get("score")
    visual_nearest = visual_dict.get("nearest_label")

    flags: list[str] = []

    spatial_disagrees = (
        spatial_score is not None and spatial_score < SPATIAL_OUTLIER_THRESHOLD
    )
    # Defensive: visual disagreement requires both a score AND a non-empty alternate.
    # If a future visual path returns nearest_label without score, don't treat as disagreement.
    visual_disagrees = (
        visual_score is not None
        and visual_nearest is not None
        and visual_nearest != element["label"]
    )

    spatial_agrees = (
        spatial_score is not None and spatial_score >= SPATIAL_OUTLIER_THRESHOLD
    )
    visual_agrees = (
        visual_score is not None
        and visual_nearest is not None
        and visual_nearest == element["label"]
    )

    if spatial_disagrees:
        flags.append("spatial_outlier")
    if visual_disagrees:
        flags.append("visual_label_mismatch")

    confidence = _weighted_confidence(
        spatial_score=spatial_score,
        visual_score=visual_score,
    )

    verdict = _decide_verdict(
        spatial_disagrees=spatial_disagrees,
        visual_disagrees=visual_disagrees,
        spatial_agrees=spatial_agrees,
        visual_agrees=visual_agrees,
        visual_nearest=visual_nearest,
    )

    return VerifyResult(
        id=element["id"],
        label=element["label"],
        confidence=confidence,
        signals={"spatial": spatial_dict, "visual": visual_dict},
        flags=flags,
        verdict=verdict,
    )


def _weighted_confidence(
    *,
    spatial_score: float | None,
    visual_score: float | None,
) -> float:
    """Renormalized weighted average of available signals.

    DOM signal is always present (the element comes with a DOM label) and trusts
    itself at 1.0. Cold-start signals are excluded from the average rather than
    counted as 0 - per brief, missing signals don't penalize.
    """
    available: dict[str, float] = {"dom": 1.0}
    if spatial_score is not None:
        available["spatial"] = spatial_score
    if visual_score is not None:
        available["visual"] = visual_score

    total_weight = sum(SIGNAL_WEIGHTS[k] for k in available)
    if total_weight == 0.0:
        return 0.0
    weighted = sum(SIGNAL_WEIGHTS[k] * available[k] for k in available)
    return weighted / total_weight


def _decide_verdict(
    *,
    spatial_disagrees: bool,
    visual_disagrees: bool,
    spatial_agrees: bool,
    visual_agrees: bool,
    visual_nearest: str | None,
) -> Verdict:
    """Verdict per brief:
      - rejected: both signals disagree AND visual has an alternate label
      - flagged:  any signal disagrees, OR no signal actively agrees (cold-start both)
      - confirmed: at least one non-DOM signal actively agrees, no signal disagrees
    Cold-start is "neither agree nor disagree" - never auto-confirms.
    """
    if spatial_disagrees and visual_disagrees and visual_nearest is not None:
        return "rejected"
    if spatial_disagrees or visual_disagrees:
        return "flagged"
    if spatial_agrees or visual_agrees:
        return "confirmed"
    # Both signals cold-start: no evidence to confirm or reject.
    return "flagged"
