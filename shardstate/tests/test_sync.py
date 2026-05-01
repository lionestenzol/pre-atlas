import os
import tempfile

import pytest

from shardstate import Store
from shardstate.sync import (
    MSG_WANT_INDEX,
    MSG_WANT_NODE,
    SyncRequest,
    pull_state,
    serve,
)


@pytest.fixture
def two_stores():
    with tempfile.TemporaryDirectory() as d:
        a = Store(os.path.join(d, "a.db"), agent_id="agent_a")
        b = Store(os.path.join(d, "b.db"), agent_id="agent_b")
        yield a, b
        a.close()
        b.close()


def _direct_transport(server: Store):
    """A `send_recv` that hands each request straight to `serve` on `server`."""

    def send_recv(req: SyncRequest) -> SyncRequest:
        resp = serve(server, req)
        assert resp is not None, f"serve returned None for {req.message_type}"
        return resp

    return send_recv


def test_pull_state_converges(two_stores):
    a, b = two_stores
    node = a.put({"type": "client", "name": "Marcus"})
    a.patch(node.id, {"name": "Marcus Aurelius"})
    target = a.head().hash

    pull_state(b, target, _direct_transport(a))

    assert b.head().hash == target
    assert b.get(node.id) == {"type": "client", "name": "Marcus Aurelius"}


def test_pull_state_multiple_entities(two_stores):
    a, b = two_stores
    n1 = a.put({"k": 1}, stable_id="e1")
    n2 = a.put({"k": 2}, stable_id="e2")
    a.patch(n1.id, {"k": 10})
    target = a.head().hash

    pull_state(b, target, _direct_transport(a))

    assert b.head().hash == target
    assert b.get("e1") == {"k": 10}
    assert b.get("e2") == {"k": 2}
    assert n2.id == "e2"


def test_pull_state_out_of_order_responses(two_stores):
    """Reverse the order in which want_node responses are answered.

    The transport here is still call-paired (request and response in the
    same call), but we map each incoming `want_node` request to the
    response for a *different* `want_node` — the one at the mirror
    position. The client should still converge: node insertions are keyed
    by content hash and the final `_install_remote_state` only runs after
    every node is in.
    """
    a, b = two_stores
    a.put({"k": 1}, stable_id="e1")
    a.put({"k": 2}, stable_id="e2")
    a.put({"k": 3}, stable_id="e3")
    target = a.head().hash

    # Pre-compute index and node responses up front, then hand them back
    # to the client in reverse order of arrival.
    index_resp = serve(a, SyncRequest(MSG_WANT_INDEX, bytes.fromhex(target)))
    assert index_resp is not None
    from shardstate.sync import _decode_index, _encode_want_node

    index = _decode_index(index_resp.payload)
    node_responses_reversed = [
        serve(a, SyncRequest(MSG_WANT_NODE, _encode_want_node(sid, ch)))
        for sid, ch, _ in reversed(index)
    ]

    pulled_index = False
    node_calls = 0

    def reordering(req: SyncRequest) -> SyncRequest:
        nonlocal pulled_index, node_calls
        if req.message_type == MSG_WANT_INDEX:
            pulled_index = True
            return index_resp
        if req.message_type == MSG_WANT_NODE:
            # Reply with whichever node response is next in our reversed
            # buffer — definitely not the one the client asked for.
            resp = node_responses_reversed[node_calls]
            node_calls += 1
            return resp
        raise AssertionError(f"unexpected message type {req.message_type}")

    pull_state(b, target, reordering)

    assert pulled_index
    assert node_calls == 3
    assert b.head().hash == target
    assert b.get("e1") == {"k": 1}
    assert b.get("e2") == {"k": 2}
    assert b.get("e3") == {"k": 3}


def test_serve_unknown_state_raises(two_stores):
    a, _ = two_stores
    fake = "deadbeef" * 4
    with pytest.raises(Exception):
        serve(a, SyncRequest(MSG_WANT_INDEX, bytes.fromhex(fake)))


def test_serve_returns_none_for_unknown_have_state(two_stores):
    from shardstate.sync import MSG_WANT_STATE
    a, _ = two_stores
    fake = "deadbeef" * 4
    resp = serve(a, SyncRequest(MSG_WANT_STATE, bytes.fromhex(fake)))
    assert resp is None


def test_pull_state_idempotent(two_stores):
    a, b = two_stores
    node = a.put({"x": 1})
    target = a.head().hash

    pull_state(b, target, _direct_transport(a))
    head1 = b.head().hash
    pull_state(b, target, _direct_transport(a))
    head2 = b.head().hash

    assert head1 == head2 == target
    assert b.get(node.id) == {"x": 1}


def test_pull_state_skips_nodes_already_present(two_stores):
    a, b = two_stores
    # B already has a node with the same value (same content hash).
    a.put({"shared": True}, stable_id="shared_id")
    b.put({"shared": True}, stable_id="shared_id")
    a.put({"only_on_a": True}, stable_id="exclusive")
    target = a.head().hash

    requests_seen: list[str] = []

    def counting(req: SyncRequest) -> SyncRequest:
        requests_seen.append(req.message_type)
        resp = serve(a, req)
        assert resp is not None
        return resp

    pull_state(b, target, counting)

    # One want_index plus exactly one want_node (for the exclusive entity).
    assert requests_seen.count(MSG_WANT_INDEX) == 1
    assert requests_seen.count(MSG_WANT_NODE) == 1
    assert b.head().hash == target
