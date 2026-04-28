"""Atlas directive dispatcher.

Polls delta-kernel /api/atlas/next-directive, routes each emitted
directive to the right backend (Optogon /session/run for path-bearing
directives, Claude Code subprocess otherwise), and produces a
BuildOutput.v1 ready for upstream signal emission.

This package is the runtime that turns Atlas intent into actual
running execution. Without it, the ghost_executor adapter library
sits idle and the MAPE-K loop is open.
"""
from __future__ import annotations

from .poll import poll_once, poll_loop

__all__ = ["poll_once", "poll_loop"]
