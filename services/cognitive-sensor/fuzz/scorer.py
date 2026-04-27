"""
scorer.py — pure scoring functions. No browser/IO/Playwright import.

`score_file` consumes (expected_json, labeled_elements) and returns a result
dict ready to drop into the runner's report. `aggregate` rolls a list of
results into top-line totals.
"""
from __future__ import annotations

from typing import TypedDict


class LabeledElement(TypedDict):
    """One labeled element as observed by the runner via DOM query."""
    id: str
    tag: str


class FileResult(TypedDict):
    file_id: str
    status: str  # "pass" | "fail" | "error"
    duration_ms: int
    actual_label_count: int
    expected_min: int
    expected_max: int
    labeled_ids: list[str]
    labeled_unmatched: list[str]
    should_find_hit: list[str]
    should_find_miss: list[str]
    filter_violations: list[str]
    errors: list[str]


def score_file(
    expected: dict,
    labeled: list[LabeledElement],
    duration_ms: int,
) -> FileResult:
    """Score one fuzz file's run.

    Rules (v0.1):
      • Count bounds → strict (fail outside [min, max]).
      • Filter violations → strict (fail if any should_filter id is labeled).
      • Find hits → soft (recorded but never fails the file in v0.1).
    """
    file_id = expected.get("file_id", "?")
    expected_min = int(expected["min_labels"])
    expected_max = int(expected["max_labels"])
    find_anchors: set[str] = {e["anchor_id"] for e in expected.get("should_find", [])}
    filter_anchors: set[str] = {e["anchor_id"] for e in expected.get("should_filter", [])}

    actual_count = len(labeled)
    labeled_ids: set[str] = {el["id"] for el in labeled if el.get("id")}
    labeled_ids_ordered = [el["id"] for el in labeled if el.get("id")]
    labeled_unlabelled = [f"(no-id:{el['tag']})" for el in labeled if not el.get("id")]

    find_hit = sorted(find_anchors & labeled_ids)
    find_miss = sorted(find_anchors - labeled_ids)
    filter_violations = sorted(filter_anchors & labeled_ids)
    all_anchors = find_anchors | filter_anchors
    labeled_unmatched = sorted(
        (labeled_ids - all_anchors)
    ) + labeled_unlabelled

    count_ok = expected_min <= actual_count <= expected_max
    no_filter_violations = len(filter_violations) == 0
    status = "pass" if (count_ok and no_filter_violations) else "fail"

    return {
        "file_id": file_id,
        "status": status,
        "duration_ms": duration_ms,
        "actual_label_count": actual_count,
        "expected_min": expected_min,
        "expected_max": expected_max,
        "labeled_ids": labeled_ids_ordered,
        "labeled_unmatched": labeled_unmatched,
        "should_find_hit": find_hit,
        "should_find_miss": find_miss,
        "filter_violations": filter_violations,
        "errors": [],
    }


def make_error_result(file_id: str, error_msg: str, duration_ms: int) -> FileResult:
    """Build a result for a file that hit an error (timeout, page-load, etc)."""
    return {
        "file_id": file_id,
        "status": "error",
        "duration_ms": duration_ms,
        "actual_label_count": 0,
        "expected_min": 0,
        "expected_max": 0,
        "labeled_ids": [],
        "labeled_unmatched": [],
        "should_find_hit": [],
        "should_find_miss": [],
        "filter_violations": [],
        "errors": [error_msg],
    }


def aggregate(results: list[FileResult]) -> dict:
    """Roll up per-file results into top-line totals for the report."""
    totals = {
        "files": len(results),
        "pass": sum(1 for r in results if r["status"] == "pass"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "find_hit": sum(len(r["should_find_hit"]) for r in results),
        "find_miss": sum(len(r["should_find_miss"]) for r in results),
        "filter_violations": sum(len(r["filter_violations"]) for r in results),
    }
    return totals
