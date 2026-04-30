"""Vector clocks for concurrent-write detection.

A vector clock is {agent_id: int}. Each agent increments its own counter on
every write to a node. Concurrency is detected by comparing two clocks: if
neither dominates the other, the writes were concurrent.
"""

from __future__ import annotations

from typing import Dict


VClock = Dict[str, int]


def empty() -> VClock:
    return {}


def increment(clock: VClock, agent_id: str) -> VClock:
    out = dict(clock)
    out[agent_id] = out.get(agent_id, 0) + 1
    return out


def merge(a: VClock, b: VClock) -> VClock:
    out = dict(a)
    for k, v in b.items():
        if v > out.get(k, 0):
            out[k] = v
    return out


def dominates(a: VClock, b: VClock) -> bool:
    """True if a >= b on every component and strictly > on at least one."""
    strictly_greater = False
    for k in set(a) | set(b):
        av = a.get(k, 0)
        bv = b.get(k, 0)
        if av < bv:
            return False
        if av > bv:
            strictly_greater = True
    return strictly_greater


def concurrent(a: VClock, b: VClock) -> bool:
    if a == b:
        return False
    return not dominates(a, b) and not dominates(b, a)
