"""Code/binary fingerprinting + execution cache — port of conversation
#81 "Universal Programming Table Setup" (2025-03-07), Pre Atlas harvest
pipeline.

931 messages, 519 code blocks, most of it (228 hedge signals) circling
an ever-more-elaborate "Python <-> C++ <-> Assembly <-> Binary" AI code
database that never converges on one coherent implementation. Two
pieces recur identically across the thread's fragments and are fully
self-contained, though:

  1. `calculate_entropy` -- real, correct Shannon entropy over a byte
     string (blocks 360/etc), used alongside a SHA256 hash to
     fingerprint a compiled binary's output.
  2. an execution cache -- the thread's own last message describes it
     directly: "if code was previously executed, results are retrieved
     instantly" instead of re-running. Never actually coded in the
     harvest, only described; implemented here keyed on the source
     code's hash rather than the binary's, since re-running the same
     source is the case this repo can actually exercise without a
     C++ toolchain.
"""
import hashlib
import math
from collections import Counter


def calculate_entropy(data):
    """Shannon entropy (bits/byte) of `data`. 0.0 for empty input."""
    if not data:
        return 0.0
    length = len(data)
    counts = Counter(data)
    entropy = -sum((freq / length) * math.log2(freq / length) for freq in counts.values())
    return round(entropy, 4)


def fingerprint_bytes(data):
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "entropy": calculate_entropy(data),
        "size": len(data),
    }


class ExecutionCache:
    """Caches a function's result keyed by the hash of its source input,
    so re-running identical code returns the cached result instead of
    re-executing -- the "failsafe" the source thread's final message
    described but never implemented."""

    def __init__(self):
        self._cache = {}

    def _key(self, code):
        return hashlib.sha256(code.encode()).hexdigest()

    def run(self, code, executor):
        """Run `executor(code)` unless a cached result exists for this
        exact code, in which case return that instead."""
        key = self._key(code)
        if key in self._cache:
            return self._cache[key], True  # (result, was_cached)
        result = executor(code)
        self._cache[key] = result
        return result, False

    def __contains__(self, code):
        return self._key(code) in self._cache
