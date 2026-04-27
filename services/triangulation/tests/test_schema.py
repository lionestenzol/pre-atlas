from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from triangulation import ElementInput, SpatialSignal, VerifyResult, Verdict, VisualSignal


def test_element_input_frozen() -> None:
    element = ElementInput(
        id="el-1",
        label="button",
        bbox=(1.0, 2.0, 3.0, 4.0),
        parent_id=None,
        screenshot_path="/x.png",
        page_id="p1",
    )

    with pytest.raises(FrozenInstanceError):
        element.label = "link"  # type: ignore[misc]


@pytest.mark.parametrize("bbox", [[10, 20, 30, 40], (10, 20, 30, 40)])
def test_element_input_from_dict(bbox: list[int] | tuple[int, int, int, int]) -> None:
    element = ElementInput.from_dict(
        {
            "id": "el-1",
            "label": "button",
            "bbox": bbox,
            "parent_id": "root",
            "screenshot_path": "/x.png",
            "page_id": "p1",
        }
    )

    assert element.bbox == (10, 20, 30, 40)
    assert element.parent_id == "root"


def test_element_input_from_dict_rejects_bad_bbox() -> None:
    with pytest.raises(ValueError, match="bbox must have 4 elements"):
        ElementInput.from_dict(
            {
                "id": "el-1",
                "label": "button",
                "bbox": [10, 20, 30],
                "parent_id": None,
                "screenshot_path": "/x.png",
                "page_id": "p1",
            }
        )


def test_element_input_to_dict_roundtrip() -> None:
    original = ElementInput(
        id="el-1",
        label="button",
        bbox=(10, 20, 30, 40),
        parent_id="root",
        screenshot_path="/x.png",
        page_id="p1",
    )

    serialized = original.to_dict()
    reloaded = ElementInput.from_dict(serialized)

    assert serialized["bbox"] == [10, 20, 30, 40]
    assert reloaded == original


def test_spatial_signal_defaults() -> None:
    signal = SpatialSignal(score=0.75)

    assert signal.alignment_groups == []
    assert signal.notes == []


def test_visual_signal_cold_start_defaults() -> None:
    signal = VisualSignal()

    assert signal.score is None
    assert signal.nearest_label is None
    assert signal.distance is None


def test_verify_result_construction() -> None:
    result = VerifyResult(
        id="el-1",
        label="button",
        confidence=0.9,
        signals={"spatial": {"score": 0.8}, "visual": {"score": 0.7}},
        flags=["spatial_outlier"],
        verdict="flagged",
    )

    assert result.id == "el-1"
    assert result.label == "button"
    assert result.confidence == pytest.approx(0.9)
    assert result.flags == ["spatial_outlier"]
    assert result.verdict == "flagged"


def test_verify_result_to_dict_with_signal_dataclasses() -> None:
    result = VerifyResult(
        id="el-1",
        label="button",
        confidence=0.8,
        signals={
            "spatial": SpatialSignal(score=0.6, alignment_groups=[["a", "b"]]),
            "visual": VisualSignal(score=0.7, nearest_label="button", distance=0.3),
        },
        verdict="confirmed",
    )

    serialized = result.to_dict()

    assert serialized["signals"]["spatial"] == {
        "score": 0.6,
        "alignment_groups": [["a", "b"]],
        "notes": [],
    }
    assert serialized["signals"]["visual"] == {
        "score": 0.7,
        "nearest_label": "button",
        "distance": 0.3,
    }


def test_verify_result_behavioral_score_default_none() -> None:
    result = VerifyResult(
        id="el-1",
        label="button",
        confidence=1.0,
        signals={"spatial": {}, "visual": {}},
    )

    assert result.behavioral_score is None


def test_verdict_literal_values() -> None:
    assert set(get_args(Verdict)) == {"confirmed", "flagged", "rejected"}

