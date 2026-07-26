"""Learned execution router — port of conversation #359 "Introduction to
Binary Code" (2025-02-24), Pre Atlas harvest pipeline.

The source thread's 181 code blocks were not JSON schemas (despite the
triage note) -- they were console-output examples from a simulated
"self-evolving PNG execution network": nodes ("PNG_1", "PNG_2", ...) each
hold a set of function keys they can execute, a shared routing table maps
function name -> the node currently assigned to handle it, and nodes
"learn" new functions by acquiring them (updating the routing table so
future requests route directly instead of forwarding). This module
implements that actual pattern -- a minimal handler registry with routing
and learning -- rather than the PNG-file framing, which was never more
than a naming convention for the toy node IDs in the transcript.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    handled_by: str
    forwarded_from: str | None = None


class LearnedExecutionRouter:
    """Routes named tasks to whichever node currently owns them, with a
    real handler function per (node, task) registered explicitly --
    'PNG_1 knows hashing_function' in the source examples means node PNG_1
    has a real callable registered for hashing_function."""

    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, object]] = {}
        self._routing_table: dict[str, str] = {}

    def register(self, node: str, task_name: str, handler) -> None:
        """Give `node` a real handler for `task_name`. First registration
        for a task_name also becomes its initial routing entry."""
        self._handlers.setdefault(node, {})[task_name] = handler
        self._routing_table.setdefault(task_name, node)

    def learn(self, node: str, task_name: str) -> None:
        """Node acquires an existing task's handler from whichever node
        currently owns it, and becomes the new routing target -- mirrors
        the source's 'PNG_1 Learning: Acquired compression_function'."""
        current_owner = self._routing_table.get(task_name)
        if current_owner is None:
            raise KeyError(f"no node currently handles {task_name!r}")
        handler = self._handlers[current_owner][task_name]
        self._handlers.setdefault(node, {})[task_name] = handler
        self._routing_table[task_name] = node

    def execute(self, task_name: str, requesting_node: str | None = None):
        """Route task_name to its current owner and run it. If
        requesting_node differs from the owner, the result records that
        the call was forwarded -- mirrors 'PNG_5 forwarded hashing_function
        to PNG_001, which executed it successfully.'"""
        owner = self._routing_table.get(task_name)
        if owner is None:
            raise KeyError(f"no node handles {task_name!r}")

        handler = self._handlers[owner][task_name]
        output = handler()
        forwarded_from = requesting_node if requesting_node and requesting_node != owner else None
        return output, ExecutionResult(handled_by=owner, forwarded_from=forwarded_from)

    def routing_table(self) -> dict[str, str]:
        return dict(self._routing_table)
