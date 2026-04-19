"""Burden-Removal inference rules.

Rules live on individual node definitions, but starter rules can be shared
across paths. Per doctrine/03_OPTOGON_SPEC.md Section 9.
"""
from __future__ import annotations
from typing import Any

from .config import AUTO_CONFIRM_CONFIDENCE
from .context import set_tier


def apply_node_rules(
    rules: list[dict[str, Any]],
    context: dict[str, dict[str, Any]],
) -> list[tuple[str, Any, float]]:
    """Apply a node's inference_rules against the current context.

    Rules have shape {key, condition, confidence, confidence_source, reversible, risk_tier}.
    Condition is a Python expression that reads from context.system/user/inferred/confirmed.
    Returns list of (key, inferred_value, confidence) triples that were actually applied
    (confidence >= the rule's own floor and eval() returned non-None).
    """
    applied: list[tuple[str, Any, float]] = []
    for rule in rules or []:
        key = rule.get("key")
        condition = rule.get("condition", "")
        confidence = float(rule.get("confidence", 0.0))
        if not key or not condition:
            continue
        try:
            value = _safe_eval(condition, context)
        except Exception:
            continue
        if value is None:
            continue
        # Write to inferred; promote to confirmed if confidence is high
        tier = "confirmed" if confidence >= AUTO_CONFIRM_CONFIDENCE else "inferred"
        set_tier(context, tier, key, value)
        applied.append((key, value, confidence))
    return applied


def _safe_eval(expr: str, context: dict[str, dict[str, Any]]) -> Any:
    """Evaluate a condition expression in a sandbox with only context tiers exposed.

    Intentionally narrow: rule expressions are path-authored data, not user input.
    Still, restrict builtins and globals.
    """
    safe_globals: dict[str, Any] = {"__builtins__": {}}
    safe_locals: dict[str, Any] = {
        "confirmed": context.get("confirmed", {}),
        "user": context.get("user", {}),
        "inferred": context.get("inferred", {}),
        "system": context.get("system", {}),
    }
    return eval(expr, safe_globals, safe_locals)  # noqa: S307 - intentional sandbox


# --- Starter cross-path rules (data, not hardcoded) -------------------------
# Loaded by paths that opt-in via their defaults. Each returns value-or-None.

STARTER_RULES: list[dict[str, Any]] = [
    {
        "key": "working_directory",
        "condition": "system.get('working_directory')",
        "confidence": 1.0,
        "confidence_source": "static",
        "reversible": True,
        "risk_tier": "low",
    },
    {
        "key": "theme",
        "condition": "'light' if system.get('product') == 'inpact' else None",
        "confidence": 0.95,
        "confidence_source": "static",
        "reversible": True,
        "risk_tier": "low",
    },
    {
        "key": "preferred_commit_prefix",
        "condition": "'feat(inpact)' if confirmed.get('path_id') == 'ship_inpact_lesson' else None",
        "confidence": 0.88,
        "confidence_source": "static",
        "reversible": True,
        "risk_tier": "low",
    },
]
