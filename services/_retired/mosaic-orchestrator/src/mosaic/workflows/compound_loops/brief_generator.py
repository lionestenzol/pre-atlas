"""Compound brief generator.

Produces a human-readable markdown brief showing cross-domain leverage,
following the style of governor_daily.py daily_brief.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult


def _score_bar(score: float, width: int = 10) -> str:
    """Generate a text progress bar for a domain score."""
    filled = round(score / 100 * width)
    return "▓" * filled + "░" * (width - filled)


def _severity_icon(severity: str) -> str:
    icons = {"HIGH": "!", "MEDIUM": "~", "LOW": "+"}
    return icons.get(severity, "?")


def generate_compound_brief(
    snapshot: CompoundSnapshot,
    loop_results: dict[str, LoopResult],
    compound_score: int,
    domain_scores: dict[str, float],
) -> str:
    """Generate actionable text showing cross-domain leverage.

    Args:
        snapshot: Immutable data snapshot.
        loop_results: Results from all 6 loops.
        compound_score: Aggregate 0-100 score.
        domain_scores: Per-domain 0-100 scores.

    Returns:
        Markdown-formatted compound brief.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode = "UNKNOWN"
    risk = "MEDIUM"
    if "error" not in snapshot.daily_payload:
        mode = snapshot.daily_payload.get("mode", "UNKNOWN")
        risk = snapshot.daily_payload.get("risk", "MEDIUM")

    lines: list[str] = []

    # Header
    lines.append(f"## Compound Brief — {now}")
    lines.append("")
    lines.append(f"**Score: {compound_score}/100** | Mode: {mode} | Risk: {risk}")
    lines.append("")

    # Domain Health
    lines.append("### Domain Health")
    domain_labels = {
        "project": "Project",
        "skill": "Skill",
        "network": "Network",
        "finance": "Finance",
        "energy": "Energy",
        "risk": "Risk",
    }
    for key, label in domain_labels.items():
        score = domain_scores.get(key, 50)
        bar = _score_bar(score)
        status = "CRITICAL" if score < 30 else ("OK" if score >= 60 else "LOW")
        lines.append(f"- {label}: {bar} {score:.0f}/100 — {status}")
    lines.append("")

    # Cross-Domain Signals
    fired_loops = {k: v for k, v in loop_results.items() if v.fired}
    if fired_loops:
        lines.append("### Cross-Domain Signals")
        for name, result in fired_loops.items():
            lines.append(f"- **{name}**: {result.output_summary}")
        lines.append("")

    # Active Constraints
    all_constraints: list[dict[str, str]] = []
    for result in loop_results.values():
        if result.signal_delta and "constraints" in result.signal_delta:
            all_constraints.extend(result.signal_delta["constraints"])

    if all_constraints:
        lines.append("### Active Constraints")
        for c in all_constraints:
            icon = _severity_icon(c.get("severity", "LOW"))
            lines.append(
                f"- [{icon}] {c.get('source_domain', '?')} → {c.get('target_domain', '?')}: "
                f"{c.get('constraint', '')}"
            )
        lines.append("")

    # Leverage Move — single highest-impact action
    lines.append("### Leverage Move")
    leverage = _compute_leverage_move(compound_score, domain_scores, fired_loops)
    lines.append(f"- {leverage}")
    lines.append("")

    return "\n".join(lines)


def _compute_leverage_move(
    compound_score: int,
    domain_scores: dict[str, float],
    fired_loops: dict[str, LoopResult],
) -> str:
    """Determine the single highest-leverage action based on compound analysis."""
    # Find the weakest domain
    if not domain_scores:
        return "Collect more data to determine leverage."

    weakest = min(domain_scores, key=lambda k: domain_scores[k])
    weakest_score = domain_scores[weakest]

    if weakest == "energy" and weakest_score < 30:
        return "RECOVER: Energy is critical. Rest before executing. All other domains depend on this."
    if weakest == "risk" and weakest_score < 30:
        return "STABILIZE: High drift detected. Close one loop today to break the pattern."
    if weakest == "project" and weakest_score < 30:
        return "CLOSE: Project health critical. Focus on closing the oldest open loop."
    if weakest == "finance" and weakest_score < 30:
        return "SHIP: Financial pressure high. Complete and ship one revenue-generating asset."
    if weakest == "network" and weakest_score < 30:
        return "CONNECT: Network is the bottleneck. One outreach action unlocks skill leverage."
    if weakest == "skill" and weakest_score < 30:
        return "LEARN: Skill growth stalled. Apply skills to close a technical loop."

    # No critical domain — compound growth mode
    if compound_score >= 70:
        return "COMPOUND: All domains healthy. Scale the highest-leverage lane."
    if compound_score >= 50:
        return f"GROW: Strengthen {weakest} ({weakest_score:.0f}/100) to unlock next compound level."

    return f"FOCUS: Raise {weakest} ({weakest_score:.0f}/100) above 50 to stabilize compound growth."
