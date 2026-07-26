"""
Shared word-boundary substring matcher for the corpus-archaeology festival.

Replaces the v1 literal `s in text.lower()` rule that fired on substrings
inside longer words (e.g. seed `stem` matching inside `system`).

Used by:
  expand_clusters.py
  validate_clusters.py
  build_era_matrix.py
  ship_flow.py

Rule: a seed matches only if it's bordered on each side by either a non-alphanumeric-underscore
character or string start/end. This is stricter than Python's `\b` because `\b` is only a transition
boundary and doesn't fire when both sides are non-word (e.g. seed `/weapon` preceded by space —
both `/` and ` ` are non-word, so `\b` fails). Lookbehind/lookahead `(?<![a-z0-9_])SEED(?![a-z0-9_])`
handles both word-only seeds (`stem` no-match in `system`) and punctuation-prefixed seeds
(`/weapon` matches in `ran /weapon today`).
"""

from __future__ import annotations

import re

# Compile once per seed-list call site is overkill; a small lru_cache on the pattern is fine.
from functools import lru_cache


@lru_cache(maxsize=1024)
def _compile_seed(s_lc: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9_]){re.escape(s_lc)}(?![a-z0-9_])")


def has_seed_match(text: str | None, seeds_lc: list[str]) -> bool:
    """Return True if any seed matches text with strict boundary rule.

    text: arbitrary text (will be lowercased).
    seeds_lc: list of seed terms, already lowercased.
    """
    if not text:
        return False
    tl = text.lower()
    for s in seeds_lc:
        if not s:
            continue
        if _compile_seed(s).search(tl):
            return True
    return False


def first_seed_match(text: str | None, seeds_lc: list[str]) -> str | None:
    """Return the first seed (in iteration order) that matches text, or None.
    Used by ship_flow to report matched_seed_term."""
    if not text:
        return None
    tl = text.lower()
    for s in seeds_lc:
        if not s:
            continue
        if _compile_seed(s).search(tl):
            return s
    return None


def _self_check() -> None:
    """Self-test executable as `python _match.py`."""
    # Negative cases (the v1 false positives that motivated this util)
    assert not has_seed_match("Bartering Dual Economy System", ["stem"]), (
        "stem must NOT match inside system"
    )
    assert not has_seed_match("Manifesting Through Desire", ["fest"]), (
        "fest must NOT match inside Manifesting"
    )
    assert not has_seed_match("infestation pattern", ["fest"]), (
        "fest must NOT match inside infestation"
    )
    assert not has_seed_match("Document Processing System Design", ["stem"]), (
        "stem must NOT match inside System"
    )

    # Positive cases (real matches must still work)
    assert has_seed_match("STRUDEL release notes", ["strudel"]), (
        "strudel must match STRUDEL as whole word"
    )
    assert has_seed_match("STEMai stem player", ["stem"]), (
        "stem must match stem-as-whole-word (after 'STEMai')"
    )
    assert has_seed_match("Stem player tutorial", ["stem"]), (
        "stem must match as a standalone word"
    )
    assert has_seed_match("anatomy-extension shipped", ["anatomy-extension"]), (
        "hyphenated seed should match"
    )
    # Word-boundary does NOT match seed-inside-alphanumeric-token:
    #   `\bmandelbulb\b` does NOT match `mandelbulb3d` because b->3 is not a word boundary.
    # This is by design — the seed list must enumerate explicit forms (mandelbulb, mandelbulb3d).
    assert not has_seed_match("Mandelbulb3D as a Forge", ["mandelbulb"]), (
        "by-design: mandelbulb seed alone does NOT match mandelbulb3d; add mandelbulb3d explicitly"
    )
    assert has_seed_match("Mandelbulb3D as a Forge", ["mandelbulb3d"]), (
        "explicit mandelbulb3d seed matches"
    )

    # Edge: punctuation as boundary
    assert has_seed_match("ran /weapon today", ["/weapon"]), (
        "/weapon should match — slash is non-word boundary"
    )

    # First-seed-match returns the matching seed
    assert first_seed_match("STRUDEL update", ["strudel", "stem"]) == "strudel"
    assert first_seed_match("nothing here", ["stem", "fest"]) is None

    print("_match.py self-check OK")


if __name__ == "__main__":
    _self_check()
