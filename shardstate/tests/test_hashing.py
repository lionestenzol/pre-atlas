from shardstate.hashing import canonical_json, hash_value


def test_canonical_json_is_key_order_independent():
    a = {"a": 1, "b": [1, 2, 3], "c": {"x": True, "y": None}}
    b = {"c": {"y": None, "x": True}, "b": [1, 2, 3], "a": 1}
    assert canonical_json(a) == canonical_json(b)


def test_hash_value_is_deterministic():
    v = {"type": "agreement", "version": 2, "terms": ["a", "b"]}
    assert hash_value(v) == hash_value(dict(v))


def test_hash_value_changes_on_change():
    v1 = {"version": 2}
    v2 = {"version": 3}
    assert hash_value(v1) != hash_value(v2)
