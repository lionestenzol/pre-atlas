"""SQLite TTL cache."""

import time

from search_stack import cache


def test_put_get_roundtrip(tmp_path, monkeypatch):
    from search_stack import cache as cache_mod
    monkeypatch.setattr(cache_mod, "DB_PATH", tmp_path / "cache.db")

    cache.put("exa", "web", "react hooks", 10, [{"title": "T", "url": "u"}])
    got = cache.get("exa", "web", "react hooks", 10)
    assert got == [{"title": "T", "url": "u"}]


def test_miss_returns_none(tmp_path, monkeypatch):
    from search_stack import cache as cache_mod
    monkeypatch.setattr(cache_mod, "DB_PATH", tmp_path / "cache.db")
    assert cache.get("exa", "web", "never-cached", 10) is None


def test_ttl_expiry(tmp_path, monkeypatch):
    from search_stack import cache as cache_mod
    monkeypatch.setattr(cache_mod, "DB_PATH", tmp_path / "cache.db")

    cache.put("exa", "web", "ttl-test", 10, [{"x": 1}], ttl=1)
    assert cache.get("exa", "web", "ttl-test", 10) is not None
    time.sleep(1.2)
    assert cache.get("exa", "web", "ttl-test", 10) is None


def test_different_keys_dont_collide(tmp_path, monkeypatch):
    from search_stack import cache as cache_mod
    monkeypatch.setattr(cache_mod, "DB_PATH", tmp_path / "cache.db")

    cache.put("exa", "web", "q", 10, [{"v": "exa"}])
    cache.put("tavily", "web", "q", 10, [{"v": "tavily"}])
    assert cache.get("exa", "web", "q", 10) == [{"v": "exa"}]
    assert cache.get("tavily", "web", "q", 10) == [{"v": "tavily"}]
