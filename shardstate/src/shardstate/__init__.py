"""shardstate — shared-state coordination for agent fleets.

Agents pass references into a content-addressed graph instead of re-sending
context. The graph is Merkle-hashed end-to-end; every reference also commits
to the state it was made against.
"""

from .store import (
    Conflict,
    NotFound,
    Node,
    Ref,
    State,
    Store,
    StoreError,
)

__all__ = [
    "Conflict",
    "NotFound",
    "Node",
    "Ref",
    "State",
    "Store",
    "StoreError",
]
