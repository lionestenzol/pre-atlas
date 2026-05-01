"""Binary wire codec for `Ref` and state-root payloads.

A `Ref` packs to a fixed-then-variable layout that fits in 32 bytes for
typical inputs. The format is intentionally explicit (no struct format
strings hidden inside helpers) so that radio framers and steg packers
downstream can predict the byte layout without reading code.

Layout of `pack_ref(ref)`::

    offset  size  field
    ------  ----  ---------------------------------------------
    0       16    state hash (raw bytes; hex of ref.state decoded)
    16      1     N = len(stable_id_utf8), unsigned byte
    17      N     stable_id as UTF-8
    17+N    1     M = len(op_utf8), unsigned byte
    18+N    M     op as UTF-8

`pack_state_root` is just the 16 raw state-hash bytes — used as a tiny
"have_state" / "want_state" sync ping.
"""

from __future__ import annotations

import struct

from .store import Ref

# State hash is BLAKE2b-128, so 16 raw bytes (32 hex chars). Mirrors
# `hashing.HASH_BYTES`; duplicated here so wire.py is self-contained
# for downstream framers that import it without the rest of the package.
STATE_HASH_BYTES = 16

# Single unsigned byte length prefix. Caps stable_id at 255 — well above
# the assert ceiling of 64 — and caps op at 255, plenty for typed labels.
_LEN_PREFIX = ">B"
_LEN_PREFIX_BYTES = 1

# Hard cap for stable_id: keeps a typical Ref under 32 bytes
# (16 + 1 + 14 + 1 + small op fits comfortably).
MAX_STABLE_ID_BYTES = 64


def pack_ref(ref: Ref) -> bytes:
    """Pack a `Ref` into a compact binary blob (≤32 bytes for typical inputs)."""
    state_raw = bytes.fromhex(ref.state)
    if len(state_raw) != STATE_HASH_BYTES:
        raise ValueError(
            f"state hash must decode to {STATE_HASH_BYTES} bytes, got {len(state_raw)}"
        )
    sid_bytes = ref.node.encode("utf-8")
    assert len(sid_bytes) <= MAX_STABLE_ID_BYTES, (
        f"stable_id exceeds {MAX_STABLE_ID_BYTES} bytes: {len(sid_bytes)}"
    )
    op_bytes = ref.op.encode("utf-8")
    if len(op_bytes) > 255:
        raise ValueError(f"op exceeds 255 bytes: {len(op_bytes)}")
    return (
        state_raw
        + struct.pack(_LEN_PREFIX, len(sid_bytes))
        + sid_bytes
        + struct.pack(_LEN_PREFIX, len(op_bytes))
        + op_bytes
    )


def unpack_ref(blob: bytes) -> Ref:
    """Inverse of `pack_ref`."""
    if len(blob) < STATE_HASH_BYTES + 2 * _LEN_PREFIX_BYTES:
        raise ValueError(f"blob too short to be a packed Ref: {len(blob)} bytes")
    state_raw = blob[:STATE_HASH_BYTES]
    cursor = STATE_HASH_BYTES
    (sid_len,) = struct.unpack_from(_LEN_PREFIX, blob, cursor)
    cursor += _LEN_PREFIX_BYTES
    sid_bytes = blob[cursor : cursor + sid_len]
    if len(sid_bytes) != sid_len:
        raise ValueError("blob truncated mid stable_id")
    cursor += sid_len
    (op_len,) = struct.unpack_from(_LEN_PREFIX, blob, cursor)
    cursor += _LEN_PREFIX_BYTES
    op_bytes = blob[cursor : cursor + op_len]
    if len(op_bytes) != op_len:
        raise ValueError("blob truncated mid op")
    cursor += op_len
    if cursor != len(blob):
        raise ValueError(f"trailing bytes after packed Ref: {len(blob) - cursor}")
    return Ref(
        state=state_raw.hex(),
        node=sid_bytes.decode("utf-8"),
        op=op_bytes.decode("utf-8"),
    )


def pack_state_root(state_hash: str) -> bytes:
    """Pack a bare state-hash for `have_state` / `want_state` pings."""
    raw = bytes.fromhex(state_hash)
    if len(raw) != STATE_HASH_BYTES:
        raise ValueError(
            f"state hash must decode to {STATE_HASH_BYTES} bytes, got {len(raw)}"
        )
    return raw


def unpack_state_root(blob: bytes) -> str:
    """Inverse of `pack_state_root`."""
    if len(blob) != STATE_HASH_BYTES:
        raise ValueError(
            f"state-root blob must be {STATE_HASH_BYTES} bytes, got {len(blob)}"
        )
    return blob.hex()
