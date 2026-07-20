import pytest

from fingerprint import calculate_entropy, fingerprint_bytes, ExecutionCache


def test_entropy_of_empty_is_zero():
    assert calculate_entropy(b"") == 0.0


def test_entropy_of_uniform_bytes_is_zero():
    assert calculate_entropy(b"aaaaaaaa") == 0.0


def test_entropy_of_two_symbols_evenly_split_is_one():
    assert calculate_entropy(b"abababab") == 1.0


def test_entropy_increases_with_symbol_diversity():
    low = calculate_entropy(b"aaaabbbb")
    high = calculate_entropy(bytes(range(256)))
    assert high > low


def test_fingerprint_bytes_reports_sha256_entropy_size():
    data = b"hello world"
    fp = fingerprint_bytes(data)
    assert fp["sha256"] == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert fp["size"] == len(data)
    assert fp["entropy"] > 0


def test_execution_cache_runs_once_for_identical_code():
    calls = []

    def executor(code):
        calls.append(code)
        return f"ran: {code}"

    cache = ExecutionCache()
    result1, was_cached1 = cache.run("print(1)", executor)
    result2, was_cached2 = cache.run("print(1)", executor)

    assert result1 == result2 == "ran: print(1)"
    assert was_cached1 is False
    assert was_cached2 is True
    assert len(calls) == 1


def test_execution_cache_distinguishes_different_code():
    cache = ExecutionCache()
    cache.run("print(1)", lambda c: "one")
    result, was_cached = cache.run("print(2)", lambda c: "two")

    assert result == "two"
    assert was_cached is False


def test_contains_reflects_cache_state():
    cache = ExecutionCache()
    assert "print(1)" not in cache
    cache.run("print(1)", lambda c: "ran")
    assert "print(1)" in cache
