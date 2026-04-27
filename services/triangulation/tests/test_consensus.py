from __future__ import annotations

from typing import Callable

import pytest

from triangulation import SpatialSignal, VisualSignal
from triangulation.config import SIGNAL_WEIGHTS
from triangulation.consensus import aggregate


ElementFactory = Callable[
    [str, str, tuple[float, float, float, float], str | None, str, str],
    dict,
]


def test_confirmed_when_no_signals_disagree(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.9, "alignment_groups": [], "notes": []},
        visual={"score": 0.7, "nearest_label": "button", "distance": 0.3},
    )

    assert result.verdict == "confirmed"
    assert result.flags == []


def test_confirmed_when_visual_cold_start(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.9, "alignment_groups": [], "notes": []},
        visual={"score": None, "nearest_label": None, "distance": None},
    )

    assert result.verdict == "confirmed"


def test_confirmed_when_spatial_lonely(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": None, "alignment_groups": [], "notes": ["element has no aligned siblings"]},
        visual={"score": 0.8, "nearest_label": "button", "distance": 0.2},
    )

    assert result.verdict == "confirmed"


def test_flagged_when_only_spatial_disagrees(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.2, "alignment_groups": [], "notes": []},
        visual={"score": 0.8, "nearest_label": "button", "distance": 0.2},
    )

    assert result.verdict == "flagged"
    assert result.flags == ["spatial_outlier"]


def test_flagged_when_only_visual_disagrees(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.9, "alignment_groups": [], "notes": []},
        visual={"score": 0.1, "nearest_label": "link", "distance": 0.2},
    )

    assert result.verdict == "flagged"
    assert result.flags == ["visual_label_mismatch"]


def test_rejected_when_both_disagree_with_visual_alternate(
    make_element: ElementFactory,
) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.2, "alignment_groups": [], "notes": []},
        visual={"score": 0.1, "nearest_label": "link", "distance": 0.2},
    )

    assert result.verdict == "rejected"
    assert result.flags == ["spatial_outlier", "visual_label_mismatch"]


def test_flagged_when_both_disagree_but_visual_no_alternate(
    make_element: ElementFactory,
) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.2, "alignment_groups": [], "notes": []},
        visual={"score": 0.1, "nearest_label": None, "distance": 0.2},
    )

    assert result.verdict == "flagged"
    assert result.flags == ["spatial_outlier"]


def test_confidence_renormalizes_when_signals_missing(
    make_element: ElementFactory,
) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": None, "alignment_groups": [], "notes": []},
        visual={"score": None, "nearest_label": None, "distance": None},
    )

    assert result.confidence == pytest.approx(1.0)


def test_confidence_weighted_average_all_three_signals(
    make_element: ElementFactory,
) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.8, "alignment_groups": [], "notes": []},
        visual={"score": 0.6, "nearest_label": "button", "distance": 0.4},
    )

    expected = (
        SIGNAL_WEIGHTS["dom"] * 1.0
        + SIGNAL_WEIGHTS["spatial"] * 0.8
        + SIGNAL_WEIGHTS["visual"] * 0.6
    ) / sum(SIGNAL_WEIGHTS.values())

    assert result.confidence == pytest.approx(expected)


def test_flags_populated_correctly(make_element: ElementFactory) -> None:
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": 0.4, "alignment_groups": [], "notes": []},
        visual={"score": 0.2, "nearest_label": "link", "distance": 0.5},
    )

    assert result.flags == ["spatial_outlier", "visual_label_mismatch"]


def test_aggregate_accepts_dataclass_or_dict(make_element: ElementFactory) -> None:
    element = make_element("el-1", "button", (0, 0, 10, 10))

    result = aggregate(
        element,
        spatial=SpatialSignal(score=0.9, alignment_groups=[["a", "b"]], notes=[]),
        visual={"score": 0.7, "nearest_label": "button", "distance": 0.3},
    )

    assert result.verdict == "confirmed"
    assert result.signals["spatial"]["alignment_groups"] == [["a", "b"]]


def test_signals_passed_through_to_result(make_element: ElementFactory) -> None:
    element = make_element("el-1", "button", (0, 0, 10, 10))
    spatial_signal = SpatialSignal(score=0.9, alignment_groups=[["a", "b"]], notes=["ok"])
    visual_signal = VisualSignal(score=0.7, nearest_label="button", distance=0.3)

    result = aggregate(element, spatial=spatial_signal, visual=visual_signal)

    assert result.signals["spatial"] == spatial_signal.to_dict()
    assert result.signals["visual"] == visual_signal.to_dict()


def test_flagged_when_both_signals_cold_start(make_element: ElementFactory) -> None:
    """Both signals unavailable - cannot confirm or reject. Per-brief 'don't penalize'
    means don't reduce confidence or flag, but ALSO don't auto-confirm without evidence.
    """
    result = aggregate(
        make_element("el-1", "button", (0, 0, 10, 10)),
        spatial={"score": None, "alignment_groups": [], "notes": []},
        visual={"score": None, "nearest_label": None, "distance": None},
    )

    assert result.verdict == "flagged"
    assert result.flags == []
    # Confidence still high because DOM trusts itself; cold-start signals don't penalize.
    assert result.confidence == pytest.approx(1.0)
