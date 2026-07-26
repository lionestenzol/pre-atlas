"""output_format JSON schemas for the genuinely agentic skills in the LangGraph
Skill Lattice (docs/LANGGRAPH_SKILL_LATTICE_PLAN.md, Seq 2).

Scope note (why only 3 skills, not the ~8 the plan's Seq 2 row names): of the
skills with real ledger volume, most already have a deterministic Receipt path
and do not need an LLM-invocation wrapper at all:
  - delta-scp, repo-inventory  -> already reachable via /seam/call (Seq 1),
    zero-LLM CLI/HTTP surfaces.
  - bearings                   -> the skill itself is explicit: "Zero LLM. Zero
    agents." Wrapping it in a real agentic session would be pure waste.
  - fest                       -> the locked plan's own NON-GOALS section says
    LangGraph should not reach into fest's Go internals; its status/list/
    validate/progress calls are plain CLI, not agentic.
  - seam                       -> a dispatcher; the Receipts it produces ARE
    already seam.v1 shaped, nothing to wrap.

That leaves the skills whose final answer genuinely requires Claude's
reasoning/tool use to produce (no shortcut CLI shells out to the same result):
code-recon, groundwork, weapon. Each schema below is built from that skill's
own SKILL.md "output contract" where one is stated explicitly (code-recon,
weapon); groundwork's is inferred from its described phases since its SKILL.md
states no single JSON shape.
"""

from __future__ import annotations

from typing import Any

CODE_RECON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "code-recon's 7-section evidence trail (SKILL.md Output contract).",
    "properties": {
        "scope": {
            "type": "string",
            "description": "What was investigated: the question being answered, the area touched.",
        },
        "search_path": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ladder rungs that fired and why (es, fd, rg, sg, semgrep, jq, yq, ctags, ...).",
        },
        "candidate_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["path", "why"],
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                },
                "required": ["claim", "file"],
            },
            "description": "Every 'I found' or 'I did not find' gets a file:line citation.",
        },
        "conclusion": {"type": "string"},
        "confidence": {"type": "string", "enum": ["confirmed", "likely", "unknown"]},
        "next_action": {"type": "string", "description": "read more, test, patch, or stop."},
        "proof": {
            "type": "string",
            "description": "Test output, `git diff --stat` line, or explicit 'no edit made because <reason>'.",
        },
    },
    "required": [
        "scope", "search_path", "candidate_files", "evidence",
        "conclusion", "confidence", "next_action", "proof",
    ],
}

GROUNDWORK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "groundwork's 3-stage pipeline result (delta-scp orient -> code-recon "
        "evidence -> fest plan), or a brownfield mastery capsule. Inferred shape "
        "-- groundwork's SKILL.md states no single JSON contract."
    ),
    "properties": {
        "mode": {"type": "string", "enum": ["plan", "brownfield_mastery"]},
        "candidate_regions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Repo regions the recon stage identified as relevant.",
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "citation_type": {"type": "string"},
                },
                "required": ["finding", "file"],
            },
        },
        "festival_ref": {
            "type": ["string", "null"],
            "description": "fest festival id, if 'plan' mode created one.",
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "dod": {"type": "string"},
                    "proof_status": {"type": "string"},
                },
                "required": ["title", "dod"],
            },
        },
        "verdict_table": {
            "type": "array",
            "description": "brownfield_mastery mode's per-claim verdict table.",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["confirmed", "busted", "partial"]},
                    "evidence": {"type": "string"},
                },
                "required": ["claim", "verdict"],
            },
        },
    },
    "required": ["mode", "candidate_regions", "evidence"],
}

WEAPON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "weapon's closed.md / mission.json shape (SKILL.md states this explicitly).",
    "properties": {
        "target": {"type": "string"},
        "status": {"type": "string", "enum": ["closed", "in_progress", "blocked"]},
        "tasks_completed": {"type": "integer"},
        "tasks_total": {"type": "integer"},
        "completion_criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "pass": {"type": "boolean"},
                },
                "required": ["name", "pass"],
            },
        },
        "cuts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicitly scoped-out items (weapon's CUT_LIST).",
        },
    },
    "required": ["target", "status", "tasks_completed", "tasks_total", "completion_criteria"],
}

# The graph-participating agentic skills and their output_format schema.
# Keys match the SKILL.md `name:` / directory name (what claude-agent-sdk's
# `skills=[...]` expects).
SKILL_SCHEMAS: dict[str, dict[str, Any]] = {
    "code-recon": CODE_RECON_SCHEMA,
    "groundwork": GROUNDWORK_SCHEMA,
    "weapon": WEAPON_SCHEMA,
}
