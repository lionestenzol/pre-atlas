"""Deterministic ops layer (Option A: registered functions).

Both devices import the same Python module of pre-registered ops. To coordinate
a state change, the sender ships only `(op_id, args, parent_state_hash)`. The
receiver looks up the op in the local registry, applies it to the same parent
state with the same args, and lands at the same new state hash. They agree
without ever shipping the result.

A registered op MUST be deterministic: given the same parent state and same
args, it produces the same new state. The `@op` decorator runs a static
`assert_deterministic` source-scan to catch obvious offenders (`time`,
`random`, `datetime.now`, `os.urandom`, `secrets`, `uuid.uuid4`, network/file
I/O modules). This is a sanity check, not a security boundary — a determined
caller can defeat it with `getattr` or import shadowing. For trusted-fleet use
the goal is to fail fast on accidents, not to sandbox hostile code.

Op-ref wire format (`op_ref_pack`) ships only the BLAKE2b digest of the args,
not the args themselves; the receiver is expected to already have the args
from a prior wire transmission. For demos and tests where args fit alongside
the ref, `op_ref_pack_inline` includes the canonical-JSON args directly.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from .hashing import canonical_json
from .store import Store


# --- Exceptions --------------------------------------------------------------


class OpError(Exception):
    """Base class for ops-layer errors."""


class OpStateMismatch(OpError):
    """Raised when `parent_state_hash` does not match the local store head."""


class NonDeterministicOp(OpError):
    """Raised when a registered op references a known nondeterministic API."""


class OpNotRegistered(OpError):
    """Raised when `run_op` is called with an unknown op name."""


# --- Registry ----------------------------------------------------------------


@dataclass(frozen=True)
class OpSpec:
    """A registered deterministic op.

    `code_hash` is BLAKE2b-128 of the function's source text. Two devices that
    register the same source will arrive at the same `code_hash`; if the source
    drifts, the hash diverges and the receiver can refuse to run.
    """

    name: str
    func: Callable[[Store, Dict[str, Any]], str]
    code_hash: str


_OPS_REGISTRY: Dict[str, OpSpec] = {}


# --- Determinism guard -------------------------------------------------------


_BANNED_MODULES = frozenset({
    "time",
    "random",
    "secrets",
    "socket",
    "asyncio",
    "threading",
    "multiprocessing",
    "subprocess",
    "requests",
    "urllib",
    "http",
    "httpx",
})

# (module, attribute) pairs that are nondeterministic but live inside
# otherwise-allowed modules.
_BANNED_ATTRS = frozenset({
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("os", "urandom"),
    ("os", "getrandom"),
    ("uuid", "uuid1"),
    ("uuid", "uuid4"),
    ("uuid", "uuid3"),
    ("uuid", "uuid5"),
})

# Standalone callables (no module qualifier) that are nondeterministic.
_BANNED_NAMES = frozenset({
    "open",  # file I/O
    "input",
})


def assert_deterministic(func: Callable[..., Any]) -> None:
    """Static source-scan for obvious nondeterminism.

    This is a sanity check, not a security boundary. It walks the function's
    AST and rejects imports of `time`, `random`, `secrets`, network/file I/O
    modules, plus calls to `datetime.now`, `os.urandom`, `uuid.uuid4`, and
    `open`. A determined author can defeat it with `getattr` or aliasing —
    the goal is to catch accidents, not adversaries.
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError) as e:
        raise NonDeterministicOp(
            f"cannot inspect source of {func!r}: {e}"
        ) from e
    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise NonDeterministicOp(
            f"cannot parse source of {func!r}: {e}"
        ) from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _BANNED_MODULES:
                    raise NonDeterministicOp(
                        f"op {func.__name__!r} imports banned module {alias.name!r}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".", 1)[0]
                if root in _BANNED_MODULES:
                    raise NonDeterministicOp(
                        f"op {func.__name__!r} imports from banned module {node.module!r}"
                    )
        elif isinstance(node, ast.Attribute):
            value = node.value
            if isinstance(value, ast.Name):
                if (value.id, node.attr) in _BANNED_ATTRS:
                    raise NonDeterministicOp(
                        f"op {func.__name__!r} references banned attribute "
                        f"{value.id}.{node.attr}"
                    )
                if value.id in _BANNED_MODULES:
                    raise NonDeterministicOp(
                        f"op {func.__name__!r} references banned module "
                        f"{value.id}.{node.attr}"
                    )
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id in _BANNED_NAMES:
                raise NonDeterministicOp(
                    f"op {func.__name__!r} calls banned builtin {target.id!r}"
                )


# --- Decorator ---------------------------------------------------------------


def op(name: str) -> Callable[[Callable[[Store, Dict[str, Any]], str]],
                              Callable[[Store, Dict[str, Any]], str]]:
    """Register `func` as the deterministic op `name`.

    The decorated function must have signature `(store: Store, args: dict) -> str`
    and return the new state hash after applying its mutation. The decorator
    runs `assert_deterministic` and computes `code_hash` from the function's
    source. Re-registering an existing name raises `OpError`.
    """

    def decorator(
        func: Callable[[Store, Dict[str, Any]], str],
    ) -> Callable[[Store, Dict[str, Any]], str]:
        if name in _OPS_REGISTRY:
            raise OpError(f"op {name!r} is already registered")
        assert_deterministic(func)
        try:
            source = textwrap.dedent(inspect.getsource(func))
        except (OSError, TypeError) as e:
            raise OpError(
                f"cannot inspect source of {func!r} to compute code_hash: {e}"
            ) from e
        code_hash = hashlib.blake2b(
            source.encode("utf-8"), digest_size=16
        ).hexdigest()
        _OPS_REGISTRY[name] = OpSpec(name=name, func=func, code_hash=code_hash)
        return func

    return decorator


# --- Runner ------------------------------------------------------------------


def run_op(
    store: Store,
    op_name: str,
    args: Dict[str, Any],
    parent_state_hash: str | None = None,
) -> Tuple[str, str]:
    """Execute a registered op against `store`.

    If `parent_state_hash` is given, the local head must match it before the
    op runs — this is how a receiver verifies "we're starting from the same
    state." Returns `(new_state_hash, code_hash)`.
    """
    spec = _OPS_REGISTRY.get(op_name)
    if spec is None:
        raise OpNotRegistered(f"op {op_name!r} is not registered")
    if parent_state_hash is not None:
        head = store.head()
        head_hash = head.hash if head is not None else None
        if head_hash != parent_state_hash:
            raise OpStateMismatch(
                f"parent_state_hash {parent_state_hash!r} does not match "
                f"local head {head_hash!r}"
            )
    new_hash = spec.func(store, args)
    return new_hash, spec.code_hash


# --- Wire format -------------------------------------------------------------


_PARENT_HASH_BYTES = 16  # matches hashing.HASH_BYTES (BLAKE2b-128 hex → 16 raw)
_ARGS_HASH_BYTES = 16


def _args_digest(args: Dict[str, Any]) -> bytes:
    return hashlib.blake2b(
        canonical_json(args), digest_size=_ARGS_HASH_BYTES
    ).digest()


def op_ref_pack(
    op_name: str, args: Dict[str, Any], parent_state_hash: str
) -> bytes:
    """Pack an op reference to ≤40 bytes for small `op_name`.

    Layout:
        16 bytes: parent_state_hash (decoded from hex)
         1 byte : op_name length N (1..255)
         N bytes: op_name (UTF-8)
        16 bytes: BLAKE2b-128 digest of canonical_json(args)

    NOTE: this format ships only the args digest, not the args themselves. The
    receiver must already have `args` from a prior channel. For demos and tests
    where args travel inline, use `op_ref_pack_inline`.
    """
    name_bytes = op_name.encode("utf-8")
    if not 1 <= len(name_bytes) <= 255:
        raise OpError(
            f"op_name must be 1..255 UTF-8 bytes (got {len(name_bytes)})"
        )
    try:
        parent_raw = bytes.fromhex(parent_state_hash)
    except ValueError as e:
        raise OpError(f"parent_state_hash is not valid hex: {e}") from e
    if len(parent_raw) != _PARENT_HASH_BYTES:
        raise OpError(
            f"parent_state_hash must decode to {_PARENT_HASH_BYTES} bytes "
            f"(got {len(parent_raw)})"
        )
    return parent_raw + bytes([len(name_bytes)]) + name_bytes + _args_digest(args)


def op_ref_unpack(blob: bytes) -> Tuple[str, str, str]:
    """Inverse of `op_ref_pack`. Returns `(op_name, args_hash_hex, parent_state_hex)`."""
    if len(blob) < _PARENT_HASH_BYTES + 1:
        raise OpError(f"op-ref too short: {len(blob)} bytes")
    parent_raw = blob[:_PARENT_HASH_BYTES]
    name_len = blob[_PARENT_HASH_BYTES]
    name_start = _PARENT_HASH_BYTES + 1
    name_end = name_start + name_len
    args_end = name_end + _ARGS_HASH_BYTES
    if len(blob) != args_end:
        raise OpError(
            f"op-ref length mismatch: expected {args_end}, got {len(blob)}"
        )
    op_name = blob[name_start:name_end].decode("utf-8")
    args_hash_hex = blob[name_end:args_end].hex()
    parent_state_hex = parent_raw.hex()
    return op_name, args_hash_hex, parent_state_hex


def op_ref_pack_inline(
    op_name: str, args: Dict[str, Any], parent_state_hash: str
) -> bytes:
    """Like `op_ref_pack`, but appends canonical-JSON args inline.

    Layout extends `op_ref_pack`:
        ... (as op_ref_pack) ...
         2 bytes: args_json length M (big-endian, 0..65535)
         M bytes: canonical_json(args)

    Use for demos and tests where args fit alongside the ref. Production wire
    (LoRa / steg) should prefer the hash-only `op_ref_pack` and ship args via a
    separate channel.
    """
    base = op_ref_pack(op_name, args, parent_state_hash)
    args_blob = canonical_json(args)
    if len(args_blob) > 0xFFFF:
        raise OpError(
            f"inline args too large: {len(args_blob)} bytes (max 65535)"
        )
    return base + len(args_blob).to_bytes(2, "big") + args_blob


def op_ref_unpack_inline(blob: bytes) -> Tuple[str, Dict[str, Any], str, str]:
    """Inverse of `op_ref_pack_inline`. Returns `(op_name, args, args_hash_hex, parent_state_hex)`."""
    import json
    if len(blob) < _PARENT_HASH_BYTES + 1:
        raise OpError(f"op-ref too short: {len(blob)} bytes")
    name_len = blob[_PARENT_HASH_BYTES]
    base_end = _PARENT_HASH_BYTES + 1 + name_len + _ARGS_HASH_BYTES
    if len(blob) < base_end + 2:
        raise OpError("inline op-ref missing args length")
    op_name, args_hash_hex, parent_state_hex = op_ref_unpack(blob[:base_end])
    args_len = int.from_bytes(blob[base_end:base_end + 2], "big")
    args_start = base_end + 2
    args_end = args_start + args_len
    if len(blob) != args_end:
        raise OpError(
            f"inline op-ref length mismatch: expected {args_end}, got {len(blob)}"
        )
    args = json.loads(blob[args_start:args_end].decode("utf-8"))
    return op_name, args, args_hash_hex, parent_state_hex
