"""Spatial geometry checks. Pure numpy. No ML.

All functions operate on element dicts with at minimum: `id`, `label`, `bbox`.
`bbox` is `(x, y, w, h)` in page pixels.

The `axis` parameter throughout means alignment axis:
- `axis='y'`: cluster by top edge (elements in the same horizontal row)
- `axis='x'`: cluster by left edge (elements in the same vertical column)

Spacing within an aligned group is computed along the perpendicular axis.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

import numpy as np

from .config import (
    ALIGNMENT_TOLERANCE_PX,
    LABEL_CONSISTENCY_THRESHOLD,
)

Axis = Literal["x", "y"]


def find_alignment_groups(
    elements: list[dict],
    axis: Axis,
    tolerance_px: int = ALIGNMENT_TOLERANCE_PX,
) -> list[list[str]]:
    """Cluster elements whose top-edge (axis='y') or left-edge (axis='x')
    falls within `tolerance_px`. Return groups of 2+ element IDs.
    """
    if axis not in ("x", "y"):
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")
    if not elements:
        return []

    edge_idx = 0 if axis == "x" else 1
    sorted_elements = sorted(elements, key=lambda e: e["bbox"][edge_idx])

    # Chain-connected (single-linkage) clustering: each new element is
    # compared to the PREVIOUS element's edge, not the group anchor. Robust
    # to slow subpixel drift across a long aligned run.
    groups: list[list[str]] = []
    current: list[str] = [sorted_elements[0]["id"]]
    prev_edge = sorted_elements[0]["bbox"][edge_idx]

    for el in sorted_elements[1:]:
        edge = el["bbox"][edge_idx]
        if abs(edge - prev_edge) <= tolerance_px:
            current.append(el["id"])
        else:
            if len(current) >= 2:
                groups.append(current)
            current = [el["id"]]
        prev_edge = edge

    if len(current) >= 2:
        groups.append(current)

    return groups


def check_spacing_regularity(group: list[dict], axis: Axis) -> float:
    """For an aligned group, compute gap regularity along the perpendicular axis.

    Returns a regularity score in [0.0, 1.0]:
      1.0 = perfectly regular (gaps identical or fewer than 3 elements)
      0.0 = chaotic (high coefficient of variation)
    Score = max(0, 1 - CV) where CV = std(gaps) / |mean(gaps)|.
    """
    if axis not in ("x", "y"):
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")
    if len(group) < 3:
        return 1.0

    # Spacing is along the OPPOSITE axis from alignment.
    spacing_idx = 0 if axis == "y" else 1
    size_idx = 2 if spacing_idx == 0 else 3

    sorted_g = sorted(group, key=lambda e: e["bbox"][spacing_idx])
    gaps: list[float] = []
    for i in range(len(sorted_g) - 1):
        a = sorted_g[i]["bbox"]
        b = sorted_g[i + 1]["bbox"]
        gap = b[spacing_idx] - (a[spacing_idx] + a[size_idx])
        gaps.append(gap)

    if not gaps:
        return 1.0

    arr = np.array(gaps, dtype=float)
    mean = float(arr.mean())
    if abs(mean) < 1e-9:
        return 1.0
    cv = float(arr.std() / abs(mean))
    return max(0.0, 1.0 - cv)


def check_label_consistency(group: list[dict]) -> dict[str, Any]:
    """Return `{majority_label, minority_labels, consistency_score}`.

    `consistency_score` = majority_count / len(group), in [0, 1].
    Empty group returns `{majority_label: None, minority_labels: [], consistency_score: 1.0}`.
    """
    if not group:
        return {
            "majority_label": None,
            "minority_labels": [],
            "consistency_score": 1.0,
        }

    labels = [el["label"] for el in group]
    counter = Counter(labels)
    majority_label, majority_count = counter.most_common(1)[0]
    minority_labels = [lab for lab in counter if lab != majority_label]
    consistency_score = majority_count / len(group)
    return {
        "majority_label": majority_label,
        "minority_labels": minority_labels,
        "consistency_score": consistency_score,
    }


def check_containment(parent: dict, children: list[dict]) -> list[str]:
    """Return IDs of children whose bboxes extend outside the parent bbox."""
    px, py, pw, ph = parent["bbox"]
    p_right = px + pw
    p_bottom = py + ph
    overflowing: list[str] = []
    for child in children:
        cx, cy, cw, ch = child["bbox"]
        if cx < px or cy < py or (cx + cw) > p_right or (cy + ch) > p_bottom:
            overflowing.append(child["id"])
    return overflowing


def score_element(element: dict, page_elements: list[dict]) -> dict[str, Any]:
    """Find which alignment groups this element belongs to and score its fit.

    Returns `{score, alignment_groups, notes}`:
      - `score`: float in [0, 1], or None when the element has no aligned siblings.
      - `alignment_groups`: list of ID lists (the groups this element is in).
      - `notes`: human-readable disagreement notes.

    Score combines `0.7 * label_fit + 0.3 * spacing_regularity`, averaged across
    all aligned groups the element belongs to. `label_fit` measures how well
    THIS element's label matches its group.
    """
    by_id = {el["id"]: el for el in page_elements}
    el_id = element["id"]

    member_groups: list[tuple[Axis, list[str]]] = []
    for axis_name in ("y", "x"):
        for group_ids in find_alignment_groups(page_elements, axis=axis_name):  # type: ignore[arg-type]
            if el_id in group_ids:
                member_groups.append((axis_name, group_ids))  # type: ignore[arg-type]

    if not member_groups:
        return {
            "score": None,
            "alignment_groups": [],
            "notes": ["element has no aligned siblings"],
        }

    notes: list[str] = []
    fit_scores: list[float] = []
    spacing_scores: list[float] = []
    alignment_group_ids: list[list[str]] = []

    for axis_name, group_ids in member_groups:
        group = [by_id[i] for i in group_ids if i in by_id]
        alignment_group_ids.append(group_ids)

        # label fit: how many group members share this element's label
        same_label_count = sum(1 for g in group if g["label"] == element["label"])
        fit = same_label_count / len(group) if group else 1.0
        fit_scores.append(fit)

        cons = check_label_consistency(group)
        if (
            cons["majority_label"] is not None
            and cons["majority_label"] != element["label"]
            and cons["consistency_score"] >= LABEL_CONSISTENCY_THRESHOLD
        ):
            notes.append(
                f"{axis_name}-aligned group: '{element['label']}' is outlier "
                f"(majority is '{cons['majority_label']}' "
                f"at {cons['consistency_score']:.0%})"
            )

        spacing_scores.append(check_spacing_regularity(group, axis_name))

    avg_fit = sum(fit_scores) / len(fit_scores)
    avg_spacing = sum(spacing_scores) / len(spacing_scores)
    score = 0.7 * avg_fit + 0.3 * avg_spacing

    return {
        "score": score,
        "alignment_groups": alignment_group_ids,
        "notes": notes,
    }
