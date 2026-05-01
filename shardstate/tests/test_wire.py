import pytest

from shardstate import Ref
from shardstate.wire import (
    MAX_STABLE_ID_BYTES,
    STATE_HASH_BYTES,
    pack_ref,
    pack_state_root,
    unpack_ref,
    unpack_state_root,
)


# A real state hash is the hex of a 16-byte digest, i.e. 32 hex chars.
_FAKE_STATE_HEX = "deadbeef" * 4


def test_pack_unpack_ref_round_trip():
    ref = Ref(state=_FAKE_STATE_HEX, node="entity_42", op="mark_done")
    blob = pack_ref(ref)
    assert unpack_ref(blob) == ref


def test_pack_ref_under_32_bytes_for_typical_inputs():
    # Typical Ship 2 Ref: short stable_id and a short op label. The format's
    # fixed overhead is state(16) + 2 length prefixes = 18 bytes, leaving
    # 14 bytes for the variable payload (stable_id + op).
    ref = Ref(state=_FAKE_STATE_HEX, node="n_abcdef01", op="read")
    blob = pack_ref(ref)
    assert len(blob) <= 32, f"packed ref is {len(blob)} bytes, expected <=32"


def test_pack_ref_layout_size_breakdown():
    # 16 + 1 + len(node) + 1 + len(op) is the exact size; assert it matches.
    ref = Ref(state=_FAKE_STATE_HEX, node="abc", op="read")
    blob = pack_ref(ref)
    assert len(blob) == STATE_HASH_BYTES + 1 + len("abc") + 1 + len("read")


def test_overlong_stable_id_rejected():
    long_sid = "x" * (MAX_STABLE_ID_BYTES + 1)
    with pytest.raises(AssertionError):
        pack_ref(Ref(state=_FAKE_STATE_HEX, node=long_sid, op="read"))


def test_non_ascii_op_round_trip():
    # UTF-8 multi-byte glyphs must survive the round trip.
    ref = Ref(state=_FAKE_STATE_HEX, node="n1", op="résumé_✓")
    blob = pack_ref(ref)
    out = unpack_ref(blob)
    assert out == ref
    assert out.op == "résumé_✓"


def test_non_ascii_stable_id_round_trip():
    ref = Ref(state=_FAKE_STATE_HEX, node="клиент_1", op="read")
    assert unpack_ref(pack_ref(ref)) == ref


def test_state_root_pack_unpack():
    blob = pack_state_root(_FAKE_STATE_HEX)
    assert len(blob) == STATE_HASH_BYTES
    assert unpack_state_root(blob) == _FAKE_STATE_HEX


def test_state_root_rejects_wrong_length():
    with pytest.raises(ValueError):
        pack_state_root("deadbeef")  # only 4 raw bytes
    with pytest.raises(ValueError):
        unpack_state_root(b"\x00" * 8)


def test_unpack_ref_rejects_truncated_blob():
    ref = Ref(state=_FAKE_STATE_HEX, node="abc", op="read")
    blob = pack_ref(ref)
    with pytest.raises(ValueError):
        unpack_ref(blob[:-1])


def test_unpack_ref_rejects_trailing_bytes():
    ref = Ref(state=_FAKE_STATE_HEX, node="abc", op="read")
    blob = pack_ref(ref) + b"\x00"
    with pytest.raises(ValueError):
        unpack_ref(blob)
