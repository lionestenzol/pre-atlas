"""Pytest wrapper that runs the script-style smoke gates as subprocesses.

These 9 files are full-featured smoke tests with their own setup/teardown and a
`run()` that ``SystemExit(0)`` on PASS (verified 2026-06-26: all 9 pass
standalone). They predate the pytest-native suite and use print/SystemExit gates
rather than ``def test_`` functions, so ``pytest`` never collected them and CI
never ran them.

Running each as a subprocess preserves its exact ``__main__`` setup/teardown and
makes ``pytest`` the single entry point that exercises every gate. This is why no
"empty test shell" was deleted — they are real tests, not stubs
(verify-before-delete). See ~/.claude/rules/common/code-as-furniture.md.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent

# Script-style smoke gates: each has a `run()`/`__main__` that exits 0 on PASS.
SMOKE_GATES = [
    "test_graph.py",
    "test_tools.py",
    "test_drops.py",
    "test_dropstore.py",
    "test_persist.py",
    "test_intake.py",
    "test_atlas_emit.py",
    "test_atlas_signal.py",
    "test_server.py",
]


@pytest.mark.parametrize("gate", SMOKE_GATES)
def test_smoke_gate(gate: str) -> None:
    """Each legacy script-style smoke gate must exit 0 (its own PASS contract)."""
    proc = subprocess.run(
        [sys.executable, gate],
        cwd=str(_HERE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"{gate} failed (rc={proc.returncode})\n"
        f"--- stdout tail ---\n{proc.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{proc.stderr[-1000:]}"
    )
