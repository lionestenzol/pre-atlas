"""Per-provider budget guard."""

from search_stack import budget


def test_consume_increments(tmp_path, monkeypatch):
    from search_stack import budget as bud
    monkeypatch.setattr(bud, "DB_PATH", tmp_path / "budget.db")

    assert budget.consume("exa", quota=100) is True
    snap = budget.snapshot("exa", quota=100)
    assert snap.used == 1
    assert snap.blocked is False


def test_block_at_threshold(tmp_path, monkeypatch):
    from search_stack import budget as bud
    monkeypatch.setattr(bud, "DB_PATH", tmp_path / "budget.db")
    # default block percent is 80 → block at 8 of quota=10
    for _ in range(7):
        assert budget.consume("test_prov", quota=10) is True
    # 8th request crosses 80% → blocked
    assert budget.consume("test_prov", quota=10) is False
    snap = budget.snapshot("test_prov", quota=10)
    assert snap.blocked is True


def test_snapshot_disabled_provider(tmp_path, monkeypatch):
    from search_stack import budget as bud
    monkeypatch.setattr(bud, "DB_PATH", tmp_path / "budget.db")
    snap = budget.snapshot("never_used", quota=500)
    assert snap.used == 0
    assert snap.blocked is False
