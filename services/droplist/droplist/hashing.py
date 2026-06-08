"""Normalization, hashing, and the classification cache.

input_hash is computed over the *normalized* string so that trivially
different raw inputs (extra spaces, casing, smart quotes) hit the same
cache entry and don't re-trigger an LLM classification call.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Common voice-to-text / copy-paste artifacts -> ASCII
_SMART = {
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}


def normalize(raw: str) -> str:
    """Clean messy human input into a stable UTF-8 string.

    NFC unicode form, smart punctuation folded, control chars stripped,
    whitespace collapsed, trimmed. Casing is preserved (entities matter).
    """
    if raw is None:
        return ""
    s = unicodedata.normalize("NFC", raw)
    for bad, good in _SMART.items():
        s = s.replace(bad, good)
    s = _CTRL.sub("", s)
    s = _WS.sub(" ", s)
    return s.strip()


def input_hash(normalized: str) -> str:
    """Stable hash of normalized input (used as cache key + dedup signal)."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ClassificationCache:
    """In-process + JSONL-backed cache keyed by input_hash.

    The cache is loaded from prior packets on construction so that re-running
    a drop you've seen before never re-classifies.
    """

    def __init__(self, prior_packets: list[dict] | None = None):
        self._cache: dict[str, dict] = {}
        if prior_packets:
            for p in prior_packets:
                h = p.get("input_hash")
                if h and h not in self._cache:
                    self._cache[h] = {
                        "type": p.get("type"),
                        "domain": p.get("domain"),
                        "entities": p.get("entities", []),
                        "confidence": p.get("confidence", 0.0),
                    }

    def get(self, h: str) -> dict | None:
        return self._cache.get(h)

    def put(self, h: str, classification: dict) -> None:
        self._cache[h] = classification

    def __contains__(self, h: str) -> bool:
        return h in self._cache
