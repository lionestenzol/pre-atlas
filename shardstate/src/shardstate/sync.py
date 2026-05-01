"""Two-device sync protocol over an injected request/response transport.

The protocol is asymmetric: one peer pulls, the other serves. A pull is a
sequence of independent request/response round-trips, each carried by the
caller-supplied ``send_recv`` callable. The transport itself can reorder,
buffer, or replay responses — `pull_state` only assumes that every request
it issues eventually returns the matching response.

Message types
-------------
``want_state``   payload = 16-byte state hash; existence ping (rarely used directly)
``have_state``   payload = 16-byte state hash; ack
``want_index``   payload = 16-byte state hash
``index_blob``   payload = JSON list of ``[stable_id, content_hash_hex, vclock_dict]``
``want_node``    payload = JSON ``{"stable_id": ..., "content_hash": ...}``
``node_blob``    payload = JSON ``{"stable_id": ..., "content_hash": ..., "value": ...}``

All payloads are bytes so the same envelope can later carry packed Refs from
``wire.py`` without reshaping the transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from .store import NotFound, Store, StoreError
from .wire import pack_state_root, unpack_state_root


# Message-type constants. Defined as module-level strings so misspellings in
# `serve` fail loudly at import-time (via the dispatch dict) rather than at
# runtime on a peer we may not control.
MSG_WANT_STATE = "want_state"
MSG_HAVE_STATE = "have_state"
MSG_WANT_INDEX = "want_index"
MSG_INDEX_BLOB = "index_blob"
MSG_WANT_NODE = "want_node"
MSG_NODE_BLOB = "node_blob"


@dataclass(frozen=True)
class SyncRequest:
    """One protocol message: a typed envelope around an opaque byte payload."""

    message_type: str
    payload: bytes


# --- payload codecs ----------------------------------------------------------
# Kept as small free functions so `serve` and `pull_state` can share them and
# tests can target the wire shape directly.


def _encode_index(index: list[tuple[str, str, dict]]) -> bytes:
    return json.dumps(
        [[sid, ch, sorted(vclock.items())] for sid, ch, vclock in index],
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_index(payload: bytes) -> list[tuple[str, str, dict]]:
    raw = json.loads(payload.decode("utf-8"))
    return [(sid, ch, dict(vclock)) for sid, ch, vclock in raw]


def _encode_want_node(stable_id: str, content_hash: str) -> bytes:
    return json.dumps(
        {"stable_id": stable_id, "content_hash": content_hash},
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_want_node(payload: bytes) -> tuple[str, str]:
    obj = json.loads(payload.decode("utf-8"))
    return obj["stable_id"], obj["content_hash"]


def _encode_node_blob(stable_id: str, content_hash: str, value) -> bytes:
    return json.dumps(
        {"stable_id": stable_id, "content_hash": content_hash, "value": value},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode_node_blob(payload: bytes) -> tuple[str, str, object]:
    obj = json.loads(payload.decode("utf-8"))
    return obj["stable_id"], obj["content_hash"], obj["value"]


# --- server side -------------------------------------------------------------


def serve(store: Store, request: SyncRequest) -> Optional[SyncRequest]:
    """Handle one peer request, returning the response (or None for pure ack).

    Deterministic and side-effect free against `store` — `serve` only reads.
    """
    if request.message_type == MSG_WANT_STATE:
        state_hash = unpack_state_root(request.payload)
        if store.has_state(state_hash):
            return SyncRequest(MSG_HAVE_STATE, pack_state_root(state_hash))
        return None
    if request.message_type == MSG_WANT_INDEX:
        state_hash = unpack_state_root(request.payload)
        index = store.export_state_index(state_hash)
        return SyncRequest(MSG_INDEX_BLOB, _encode_index(index))
    if request.message_type == MSG_WANT_NODE:
        stable_id, content_hash = _decode_want_node(request.payload)
        try:
            value = store.get_node_value(content_hash)
        except NotFound as exc:
            raise StoreError(f"peer asked for unknown node {content_hash}") from exc
        return SyncRequest(MSG_NODE_BLOB, _encode_node_blob(stable_id, content_hash, value))
    raise StoreError(f"serve: unhandled message type {request.message_type!r}")


# --- client side -------------------------------------------------------------


def pull_state(
    local: Store,
    target_state_hash: str,
    send_recv: Callable[[SyncRequest], SyncRequest],
) -> None:
    """Bring `local` up to `target_state_hash` by fetching whatever it lacks.

    Steps:
      1. Pull the index for the target state.
      2. For each (stable_id, content_hash) we don't already have, request the
         node blob and store it.
      3. Install the state row + entity table from the now-complete index.

    `send_recv` is the only transport surface — the caller controls framing,
    retries, and ordering. Out-of-order delivery is fine because each call is
    its own request/response pair and node insertions commute (they're keyed
    by content hash).
    """
    if local.has_state(target_state_hash):
        # Already converged to this state; nothing to fetch.
        index = local.export_state_index(target_state_hash)
        local._install_remote_state(target_state_hash, index)
        return

    index_resp = send_recv(
        SyncRequest(MSG_WANT_INDEX, pack_state_root(target_state_hash))
    )
    if index_resp.message_type != MSG_INDEX_BLOB:
        raise StoreError(
            f"pull_state: expected {MSG_INDEX_BLOB}, got {index_resp.message_type}"
        )
    index = _decode_index(index_resp.payload)

    missing = [(sid, ch) for sid, ch, _vc in index if not local.has_node(ch)]
    for stable_id, content_hash in missing:
        node_resp = send_recv(
            SyncRequest(MSG_WANT_NODE, _encode_want_node(stable_id, content_hash))
        )
        if node_resp.message_type != MSG_NODE_BLOB:
            raise StoreError(
                f"pull_state: expected {MSG_NODE_BLOB}, got {node_resp.message_type}"
            )
        _sid, got_hash, value = _decode_node_blob(node_resp.payload)
        stored_hash = local.apply_remote_node(value)
        if stored_hash != got_hash:
            raise StoreError(
                f"pull_state: node hash mismatch (claimed={got_hash} stored={stored_hash})"
            )

    local._install_remote_state(target_state_hash, index)
