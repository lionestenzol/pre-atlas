"""Report export — JSON (schema-validated) and markdown formats."""
import json
from pathlib import Path

import jsonschema


def _load_schema() -> dict:
    """Load SimulationReport.v1.json schema."""
    # Walk up to find contracts/schemas/
    p = Path(__file__).resolve()
    for parent in p.parents:
        schema_path = parent / "contracts" / "schemas" / "SimulationReport.v1.json"
        if schema_path.exists():
            return json.loads(schema_path.read_text())
    return {}


def to_json(report: dict) -> dict:
    """Validate report against schema and return. Raises on validation failure."""
    schema = _load_schema()
    if schema:
        jsonschema.validate(instance=report, schema=schema)
    return report


def to_markdown(report: dict) -> str:
    """Convert report to human-readable markdown."""
    lines = [
        f"# Simulation Report: {report.get('topic', 'Unknown')}",
        "",
        f"**Simulation ID:** {report.get('simulation_id', 'N/A')}",
        f"**Agents:** {report.get('agent_count', 0)} | **Ticks:** {report.get('tick_count', 0)} | **Duration:** {report.get('duration_seconds', 0):.1f}s",
        f"**Generated:** {report.get('created_at', 'N/A')}",
        "",
        "## Summary",
        report.get("summary", "No summary available."),
        "",
    ]

    insights = report.get("key_insights", [])
    if insights:
        lines.append("## Key Insights")
        for insight in insights:
            lines.append(f"- {insight}")
        lines.append("")

    consensus = report.get("consensus_points", [])
    if consensus:
        lines.append("## Consensus Points")
        for cp in consensus:
            conf = cp.get("confidence", 0)
            supporting = cp.get("supporting_agents", "?")
            lines.append(f"- **{cp['claim']}** (confidence: {conf:.0%}, {supporting} agents)")
        lines.append("")

    dissent = report.get("dissent_points", [])
    if dissent:
        lines.append("## Points of Dissent")
        for dp in dissent:
            lines.append(f"- **{dp['claim']}** (for: {dp.get('agents_for', '?')}, against: {dp.get('agents_against', '?')})")
        lines.append("")

    recs = report.get("recommendations", [])
    if recs:
        lines.append("## Recommendations")
        for rec in recs:
            priority = rec.get("priority", "medium").upper()
            lines.append(f"- [{priority}] **{rec['action']}** — {rec.get('rationale', '')}")
        lines.append("")

    contributions = report.get("agent_contributions", [])
    if contributions:
        lines.append("## Agent Contributions")
        lines.append("| Agent | Archetype | Messages | Influence |")
        lines.append("|-------|-----------|----------|-----------|")
        for ac in sorted(contributions, key=lambda x: x.get("influence_score", 0), reverse=True):
            lines.append(
                f"| {ac['agent_id']} | {ac['archetype']} | {ac.get('message_count', 0)} | {ac.get('influence_score', 0):.1%} |"
            )
        lines.append("")

    return "\n".join(lines)
