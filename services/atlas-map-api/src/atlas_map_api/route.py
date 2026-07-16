"""Layer-4: free-text dispatch over the capability registry (the "librarian").

Given a query like "where am I" or "run autopilot", rank every capability the
CALLER can already see (via the same describe_surface projection /describe
uses) and return either a confident top pick or a shortlist. This is deliberately
the cheapest possible tier: no LLM, no embeddings — rapidfuzz string matching,
same engine and cutoff style as the existing /map/search over subsystems
(server.py) — but NOT the same scoring shape: see the weighting note below.

Security property: because ranking runs over describe_surface's already-gated
`fields` (not the raw overlay), a capability outside the caller's clearance is
never scored at all — the router can surface strictly less than /describe would
show the same caller, never more. It never invokes anything; callers still go
through /call or /seam/call, which apply their own gates.

Scoring: triggers vs. label, not one merged haystack
------------------------------------------------------
An earlier version scored one joined "surface | label | triggers" string per
capability. At real corpus scale (~40 surfaces, ~170 capabilities) this produced
confident-looking false positives: rapidfuzz's WRatio partial-ratio component
scores unrelated short strings surprisingly high whenever there's incidental
token/character overlap (measured: "run autopilot" scored 85 against optogon's
unrelated "Start a path session and run the first turn" label — higher than
autopilot's OWN capabilities, which only reached 57-60 on the merged haystack).
Triggers are author-curated intent signals; label/surface text is a weaker,
noisier fallback for capabilities that haven't been backfilled with triggers
yet. So they're scored SEPARATELY and combined by max(), with the label-only
signal explicitly discounted rather than trusted at face value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from . import describe as describe_mod

# A capability with no declared triggers still matches on surface+label alone,
# but that signal is real-world noisier (see module docstring) — discounted so
# a strong CURATED trigger match always outranks an accidental label overlap.
LABEL_ONLY_WEIGHT = 0.6

# Below this score a candidate isn't worth surfacing at all. Calibrated against
# the live registry (not guessed): a nonsense query's top score across every
# visible capability topped out at ~47 under this weighting scheme; every real
# trigger-backed match for its own capability cleared 55+. See tests/test_route.py.
MATCH_MIN_SCORE = 55

# At/above this score, and clear of the runner-up by CONFIDENT_GAP, the top
# match is treated as a single confident pick rather than a shortlist to choose
# from — mirrors autopilot's own decision-tree philosophy: dispatch outright
# when it's unambiguous, escalate (here: hand back a shortlist) when it's not.
# Deliberately conservative (a shortlist is always safe; a wrong confident pick
# is not) — an exact or near-exact trigger match reliably clears both.
CONFIDENT_SCORE = 85
CONFIDENT_GAP = 20


def _score(query: str, surface: str, field: dict[str, Any]) -> float:
    triggers = field.get("triggers") or []
    trigger_score = max((fuzz.WRatio(query, t) for t in triggers), default=0.0)
    label_score = fuzz.WRatio(query, f"{surface} {field.get('label', '')}")
    return max(trigger_score, label_score * LABEL_ONLY_WEIGHT)


def route(
    repo_root: Path,
    role: describe_mod.Role,
    query: str,
    limit: int = 5,
    secret: str | None = None,
) -> dict[str, Any]:
    """Rank declared capabilities against a free-text query for one caller.

    Returns {query, count, confident, matches: [{surface, capability, label,
    score, direction, criticality, invoke?, needs?}, ...]}. `matches` is sorted
    by score descending and capped at `limit`. `confident` is true only when the
    top match clears CONFIDENT_SCORE and leads the runner-up by CONFIDENT_GAP —
    callers should treat a non-confident result as "ask before invoking."
    """
    rows: list[tuple[float, str, dict[str, Any]]] = []
    for surface in describe_mod.described_surfaces(repo_root):
        overlay = describe_mod.load_overlay(repo_root, surface)
        if overlay is None or overlay.lifecycle != "live":
            continue
        form = describe_mod.describe_surface(overlay, role, secret=secret)
        for cap_field in form["fields"]:
            score = _score(query, surface, cap_field)
            if score >= MATCH_MIN_SCORE:
                rows.append((score, surface, cap_field))

    rows.sort(key=lambda r: -r[0])
    top = rows[:limit]
    matches = [
        {
            "surface": surface,
            "capability": cap_field["id"],
            "label": cap_field["label"],
            "score": round(score, 1),
            "direction": cap_field["direction"],
            "criticality": cap_field["criticality"],
            **({"invoke": cap_field["invoke"]} if "invoke" in cap_field else {}),
            **({"needs": cap_field["needs"]} if "needs" in cap_field else {}),
        }
        for score, surface, cap_field in top
    ]

    confident = False
    if matches and matches[0]["score"] >= CONFIDENT_SCORE:
        gap = matches[0]["score"] - matches[1]["score"] if len(matches) > 1 else 100
        confident = gap >= CONFIDENT_GAP

    return {"query": query, "count": len(matches), "confident": confident, "matches": matches}
