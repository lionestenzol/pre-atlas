"""Codex Dispatcher — Cortex's surface for Codex CLI delegation.

Per doctrine/02_ROSETTA_STONE.md, Cortex is the layer that dispatches AI
execution. This module hosts intent classification + Codex CLI invocation,
moved here from services/optogon/src/optogon/action_handlers.py to restore
the doctrine flow:

    Optogon -> [delegation request] -> Atlas -> [directive] -> Cortex -> Codex

Callers reach it over HTTP via POST /codex/exec (see cortex/main.py)
instead of shelling Codex directly.
"""
from .dispatcher import (
    DispatchError,
    dispatch_codex,
    classify_intent,
    run_codex_exec,
)

__all__ = [
    "DispatchError",
    "dispatch_codex",
    "classify_intent",
    "run_codex_exec",
]
