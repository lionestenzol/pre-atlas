"""Ghost Executor role - consumes Directives, emits Task Prompts and Build Outputs.

Per doctrine/02_ROSETTA_STONE.md Contracts 3 and 4. Cortex plays the Ghost
Executor role in the Optogon stack: delta-kernel (Atlas) emits Directives,
this module formats them for Claude Code as TaskPrompts, and wraps responses
as BuildOutputs.

Usage:
    from cortex.ghost_executor import consume_directive, emit_build_output
"""
from .consume import consume_directive, DirectiveInvalidError
from .emit import emit_build_output, BuildOutputInvalidError

__all__ = [
    "consume_directive",
    "emit_build_output",
    "DirectiveInvalidError",
    "BuildOutputInvalidError",
]
