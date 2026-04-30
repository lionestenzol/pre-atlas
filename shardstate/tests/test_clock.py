from shardstate import clock as vc


def test_increment_and_dominates():
    a = vc.increment(vc.empty(), "agent1")
    b = vc.increment(a, "agent1")
    assert vc.dominates(b, a)
    assert not vc.dominates(a, b)


def test_concurrent_writes_detected():
    base = vc.increment(vc.empty(), "agent1")
    left = vc.increment(base, "agent2")
    right = vc.increment(base, "agent3")
    assert vc.concurrent(left, right)
    assert not vc.dominates(left, right)
    assert not vc.dominates(right, left)


def test_merge_takes_max_per_component():
    a = {"x": 2, "y": 5}
    b = {"x": 4, "y": 1, "z": 7}
    assert vc.merge(a, b) == {"x": 4, "y": 5, "z": 7}


def test_equal_clocks_not_concurrent_not_dominating():
    a = {"agent1": 3}
    b = {"agent1": 3}
    assert not vc.concurrent(a, b)
    assert not vc.dominates(a, b)
    assert not vc.dominates(b, a)
