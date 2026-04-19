"""Tests for ghost_executor.emit_build_output."""
from __future__ import annotations
import pytest

from cortex.ghost_executor import emit_build_output, BuildOutputInvalidError


def test_emit_success_output():
    out = emit_build_output(
        task_prompt_id="tp_test_01",
        status="success",
        summary="Lesson 5 shipped cleanly",
        artifacts=[{"type": "file", "path": "apps/inpact/content/lessons/5.md"}],
        tokens_used=4200,
    )
    assert out["schema_version"] == "1.0"
    assert out["status"] == "success"
    assert out["tokens_used"] == 4200


def test_emit_bad_status_rejected():
    with pytest.raises(BuildOutputInvalidError):
        emit_build_output(
            task_prompt_id="tp_test_01",
            status="nonsense",
            summary="x",
        )


def test_emit_artifact_diff_missing_path_rejected():
    with pytest.raises(BuildOutputInvalidError):
        emit_build_output(
            task_prompt_id="tp_test_01",
            status="success",
            summary="x",
            artifacts=[{"type": "diff"}],  # path required for type=diff
        )
