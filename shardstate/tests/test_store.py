import os
import tempfile
import time

import pytest

from shardstate import NotFound, Ref, Store, StoreError


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as d:
        s = Store(os.path.join(d, "test.db"), agent_id="agent_test")
        yield s
        s.close()


def test_put_and_get(store):
    node = store.put({"type": "client", "name": "Marcus"})
    assert store.get(node.id) == {"type": "client", "name": "Marcus"}
    assert store.head().hash  # there is a head


def test_quickstart_flow(store):
    client = store.put({"type": "client", "name": "Marcus", "email": "m@example.com"})
    agreement = store.put({
        "type": "agreement",
        "version": 2,
        "payment_terms": {"due_date": "2026-05-15", "clause": "Net 30"},
        "client": client.id,
    })

    new_state = store.patch(agreement.id, {"payment_terms.due_date": "2026-06-01"})
    ref = Ref(state=new_state.hash, node=agreement.id, op="read")

    view = store.resolve(ref)
    assert view["payment_terms"]["due_date"] == "2026-06-01"
    assert view["payment_terms"]["clause"] == "Net 30"
    assert view["client"] == client.id


def test_state_hash_changes_on_any_change(store):
    n = store.put({"x": 1})
    h1 = store.head().hash
    store.patch(n.id, {"x": 2})
    h2 = store.head().hash
    assert h1 != h2


def test_state_hash_deterministic_across_stores():
    with tempfile.TemporaryDirectory() as d:
        s1 = Store(os.path.join(d, "a.db"), agent_id="agent_a")
        s2 = Store(os.path.join(d, "b.db"), agent_id="agent_a")
        n1 = s1.put({"x": 1}, stable_id="thing")
        n2 = s2.put({"x": 1}, stable_id="thing")
        # same content + same agent + same stable_id → same vclock → same state
        assert s1.head().hash == s2.head().hash
        s1.close()
        s2.close()


def test_get_at_historical_state(store):
    n = store.put({"v": 1})
    s_v1 = store.head().hash
    store.patch(n.id, {"v": 2})
    assert store.get(n.id) == {"v": 2}
    assert store.get(n.id, state=s_v1) == {"v": 1}


def test_resolve_unknown_state_fails_loudly(store):
    n = store.put({"x": 1})
    with pytest.raises(NotFound):
        store.resolve(Ref(state="deadbeef" * 4, node=n.id))


def test_resolve_unknown_node_fails_loudly(store):
    with pytest.raises(NotFound):
        store.get("nonexistent_id")


def test_patch_creates_new_immutable_node(store):
    n = store.put({"v": 1})
    h1 = n.hash
    store.patch(n.id, {"v": 2})
    # historical hash still loadable
    assert store._load_node(h1) == {"v": 1}


def test_append_to_list(store):
    n = store.put({"items": [1, 2, 3]})
    state = store.append(n.id, "items", 4)
    assert store.get(n.id, state=state.hash) == {"items": [1, 2, 3, 4]}


def test_append_rejects_non_list(store):
    n = store.put({"x": 5})
    with pytest.raises(StoreError):
        store.append(n.id, "x", "oops")


def test_patch_nested_path(store):
    n = store.put({"a": {"b": {"c": 1}}})
    store.patch(n.id, {"a.b.c": 99})
    assert store.get(n.id) == {"a": {"b": {"c": 99}}}


def test_patch_delete_sentinel(store):
    n = store.put({"a": 1, "b": 2})
    store.patch(n.id, {"a": Store.DELETE})
    assert store.get(n.id) == {"b": 2}


def test_diff_added_removed_changed(store):
    a = store.put({"v": 1}, stable_id="a")
    state_initial = store.head().hash
    store.put({"v": 1}, stable_id="b")
    store.patch("a", {"v": 2})
    state_final = store.head().hash
    diffs = {d["stable_id"]: d for d in store.diff(state_initial, state_final)}
    assert diffs["a"]["change"] == "changed"
    assert diffs["b"]["change"] == "added"


def test_subscribe_yields_new_states(store):
    base = store.head()  # may be None
    since = base.hash if base else None
    states_seen = []
    gen = store.subscribe(since=since, poll_interval=0.01, stop_after=0.5)
    n = store.put({"x": 1})
    states_seen.append(next(gen))
    store.patch(n.id, {"x": 2})
    states_seen.append(next(gen))
    assert states_seen[0].hash != states_seen[1].hash


def test_concurrent_write_logs_conflict(store):
    # Simulate two agents writing concurrently to the same entity
    n = store.put({"v": "base"}, agent_id="agent_x")
    # Local agent updates
    local_state = store.patch(n.id, {"v": "local"}, agent_id="agent_x")
    # A concurrent remote write that didn't see "local" — its clock is from base
    base_clock = {"agent_x": 1}  # the clock right after put, before local patch
    remote_clock = {"agent_x": 1, "agent_remote": 1}  # remote bumped its own component on base
    store.merge_remote(
        stable_id=n.id,
        remote_value={"v": "remote"},
        remote_clock=remote_clock,
        remote_agent="agent_remote",
    )
    conflicts = store.conflicts(n.id)
    assert len(conflicts) == 1
    assert {conflicts[0].winning_agent, conflicts[0].losing_agent} == {"agent_x", "agent_remote"}


def test_remote_dominates_accepts_outright(store):
    n = store.put({"v": 0}, agent_id="agent_x")
    # remote clock dominates local: x:1 (saw local), plus its own contribution
    remote_clock = {"agent_x": 1, "agent_y": 5}
    store.merge_remote(n.id, {"v": "remote"}, remote_clock, "agent_y")
    assert store.get(n.id) == {"v": "remote"}
    assert store.conflicts() == []


def test_local_dominates_ignores_stale_remote(store):
    n = store.put({"v": 0}, agent_id="agent_x")
    store.patch(n.id, {"v": 1}, agent_id="agent_x")
    # remote_clock is from before either local write
    store.merge_remote(n.id, {"v": "stale"}, {}, "agent_y")
    assert store.get(n.id) == {"v": 1}


def test_ref_round_trip():
    r = Ref(state="abc", node="n1", op="mark_done")
    d = r.to_dict()
    assert Ref.from_dict(d) == r


def test_agent_id_persisted_across_reopen():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "x.db")
        s1 = Store(path)
        aid = s1.agent_id
        s1.close()
        s2 = Store(path)
        assert s2.agent_id == aid
        s2.close()
