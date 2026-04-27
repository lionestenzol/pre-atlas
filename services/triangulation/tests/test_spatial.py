from __future__ import annotations

import time
from typing import Callable

import pytest

import triangulation.spatial as spatial


ElementFactory = Callable[
    [str, str, tuple[float, float, float, float], str | None, str, str],
    dict,
]
LargePageFactory = Callable[[int], list[dict]]


def test_find_alignment_groups_empty() -> None:
    assert spatial.find_alignment_groups([], axis="y") == []


def test_find_alignment_groups_single_element(lonely_element: dict) -> None:
    assert spatial.find_alignment_groups([lonely_element], axis="y") == []


def test_find_alignment_groups_y_axis_simple(nav_row: list[dict]) -> None:
    groups = spatial.find_alignment_groups(nav_row, axis="y")

    assert groups == [[element["id"] for element in nav_row]]


def test_find_alignment_groups_x_axis_column(make_element: ElementFactory) -> None:
    column = [
        make_element(f"cell-{index}", "field", (25, 20 + (index * 60), 100, 40))
        for index in range(4)
    ]

    groups = spatial.find_alignment_groups(column, axis="x")

    assert groups == [[element["id"] for element in column]]


def test_find_alignment_groups_tolerance(make_element: ElementFactory) -> None:
    elements = [
        make_element("a", "item", (10, 10, 40, 20)),
        make_element("b", "item", (60, 14, 40, 20)),
        make_element("c", "item", (110, 19, 40, 20)),
        make_element("d", "item", (160, 40, 40, 20)),
    ]

    groups = spatial.find_alignment_groups(elements, axis="y")

    assert groups == [["a", "b"]]


def test_find_alignment_groups_invalid_axis(nav_row: list[dict]) -> None:
    with pytest.raises(ValueError, match="axis must be 'x' or 'y'"):
        spatial.find_alignment_groups(nav_row, axis="z")  # type: ignore[arg-type]


def test_find_alignment_groups_chain_connected(make_element: ElementFactory) -> None:
    """Chain-connected (single-linkage) clustering: drift across an aligned run
    accumulates as long as each consecutive step is within tolerance.
    Anchor-based clustering would only catch the first 2 here.
    """
    elements = [
        make_element("a", "item", (10, 0, 40, 20)),
        make_element("b", "item", (60, 3, 40, 20)),
        make_element("c", "item", (110, 6, 40, 20)),
        make_element("d", "item", (160, 9, 40, 20)),
    ]
    groups = spatial.find_alignment_groups(elements, axis="y", tolerance_px=4)
    assert groups == [["a", "b", "c", "d"]]


def test_find_alignment_groups_1000_elements_runs_under_1s(
    large_page: LargePageFactory,
) -> None:
    elements = large_page(1000)

    start = time.monotonic()
    groups = spatial.find_alignment_groups(elements, axis="y")
    elapsed = time.monotonic() - start

    assert len(groups) == 20
    assert elapsed < 1.0


@pytest.mark.parametrize("count", [1, 2])
def test_check_spacing_regularity_under_3_elements_returns_one(
    make_element: ElementFactory,
    count: int,
) -> None:
    group = [
        make_element(f"el-{index}", "item", (10 + (index * 50), 10, 20, 20))
        for index in range(count)
    ]

    assert spatial.check_spacing_regularity(group, axis="y") == pytest.approx(1.0)


def test_check_spacing_regularity_perfect_grid(nav_row: list[dict]) -> None:
    score = spatial.check_spacing_regularity(nav_row, axis="y")

    assert score == pytest.approx(1.0)


def test_check_spacing_regularity_chaotic(make_element: ElementFactory) -> None:
    group = [
        make_element("a", "item", (10, 10, 20, 20)),
        make_element("b", "item", (45, 10, 20, 20)),
        make_element("c", "item", (140, 10, 20, 20)),
        make_element("d", "item", (165, 10, 20, 20)),
    ]

    score = spatial.check_spacing_regularity(group, axis="y")

    assert score < 0.5


def test_check_spacing_regularity_zero_mean_gaps(make_element: ElementFactory) -> None:
    group = [
        make_element("a", "item", (10, 10, 20, 20)),
        make_element("b", "item", (30, 10, 20, 20)),
        make_element("c", "item", (50, 10, 20, 20)),
    ]

    assert spatial.check_spacing_regularity(group, axis="y") == pytest.approx(1.0)


def test_check_label_consistency_uniform(nav_row: list[dict]) -> None:
    result = spatial.check_label_consistency(nav_row)

    assert result == {
        "majority_label": "nav_link",
        "minority_labels": [],
        "consistency_score": 1.0,
    }


def test_check_label_consistency_one_outlier_in_five(
    nav_row_with_outlier: list[dict],
) -> None:
    result = spatial.check_label_consistency(nav_row_with_outlier)

    assert result["majority_label"] == "nav_link"
    assert result["minority_labels"] == ["button"]
    assert result["consistency_score"] == pytest.approx(0.8)


def test_check_label_consistency_empty() -> None:
    result = spatial.check_label_consistency([])

    assert result == {
        "majority_label": None,
        "minority_labels": [],
        "consistency_score": 1.0,
    }


def test_check_containment_all_inside(
    make_element: ElementFactory,
    nav_row: list[dict],
) -> None:
    parent = make_element("parent", "nav", (0, 0, 600, 100))

    assert spatial.check_containment(parent, nav_row) == []


def test_check_containment_one_overflowing_right(make_element: ElementFactory) -> None:
    parent = make_element("parent", "frame", (0, 0, 100, 100))
    children = [make_element("child-1", "card", (90, 10, 20, 20), parent_id="parent")]

    assert spatial.check_containment(parent, children) == ["child-1"]


def test_check_containment_one_overflowing_top(make_element: ElementFactory) -> None:
    parent = make_element("parent", "frame", (10, 10, 100, 100))
    children = [make_element("child-1", "card", (20, 5, 20, 20), parent_id="parent")]

    assert spatial.check_containment(parent, children) == ["child-1"]


def test_score_element_lonely_returns_none(lonely_element: dict) -> None:
    result = spatial.score_element(lonely_element, [lonely_element])

    assert result["score"] is None
    assert result["alignment_groups"] == []
    assert result["notes"] == ["element has no aligned siblings"]


def test_score_element_in_homogeneous_group(nav_row: list[dict]) -> None:
    result = spatial.score_element(nav_row[0], nav_row)

    assert result["score"] == pytest.approx(1.0)
    assert result["alignment_groups"] == [[element["id"] for element in nav_row]]
    assert result["notes"] == []


def test_score_element_outlier_in_consistent_group(
    nav_row_with_outlier: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spatial, "LABEL_CONSISTENCY_THRESHOLD", 0.8)

    result = spatial.score_element(nav_row_with_outlier[-1], nav_row_with_outlier)

    assert result["score"] < 0.5
    assert result["notes"]
    assert "outlier" in result["notes"][0]

