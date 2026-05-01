"""shardstate — shared-state coordination for agent fleets.

Agents pass references into a content-addressed graph instead of re-sending
context. The graph is Merkle-hashed end-to-end; every reference also commits
to the state it was made against.
"""

from .ops import (
    NonDeterministicOp,
    OpError,
    OpNotRegistered,
    OpStateMismatch,
    op,
    op_ref_pack,
    op_ref_unpack,
    run_op,
)
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
    "NonDeterministicOp",
    "NotFound",
    "Node",
    "OpError",
    "OpNotRegistered",
    "OpStateMismatch",
    "Ref",
    "State",
    "Store",
    "StoreError",
    "op",
    "op_ref_pack",
    "op_ref_unpack",
    "run_op",
]
