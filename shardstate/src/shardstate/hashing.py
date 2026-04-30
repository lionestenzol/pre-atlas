"""Canonical JSON encoding + BLAKE2b hashing.

Hashes are the identity of every node and every state root. They must be
deterministic across processes, so we canonicalize before hashing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

HASH_BYTES = 16  # 128 bits — collision-resistant enough for trusted-fleet use
HASH_PREFIX_LEN = 8  # not used internally; convenience for log lines


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=HASH_BYTES).hexdigest()


def hash_value(value: Any) -> str:
    return hash_bytes(canonical_json(value))
