#!/usr/bin/env python3
"""Skill -> Receipt adapters (LangGraph Skill Lattice, Seq 2).

Invokes a genuinely agentic Claude Code Skill through `claude-agent-sdk`,
forcing its `output_format` to the skill's schema (schemas.py), and normalizes
the SDK's `structured_output` into the SAME `seam.v1` Receipt shape every other
tool in this stack already produces (`atlas_map_api.seam.Receipt`) -- so a
downstream LangGraph node (Seq 3) can treat an LLM-driven skill call and a
deterministic CLI call identically: read `status`, read `data`, done.

Unlike the CLI-wrapped surfaces in `tools/seam/run.py`, there is no tool-
printed sha256 to lift -- the skill's own reasoning IS the artifact, so the
Receipt's `sha256` is computed here, over the canonical JSON of
`structured_output` itself (the content-address of the answer, not of an
input file).

    python skill_nodes.py code-recon "locate where run_id is threaded through /seam/call"
    python skill_nodes.py weapon "close out the chatpull archive skill" --max-budget 1.00 --json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Self-contained: make atlas_map_api + this dir's sibling modules importable without
# installing anything (mirrors tools/seam/run.py). Explicit __file__-relative path, not
# CWD, so this works identically run directly OR loaded via importlib from a test.
_SRC = Path(os.environ.get(
    "ATLAS_MAP_API_SRC", "C:/Users/bruke/Pre Atlas/services/atlas-map-api/src"))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from atlas_map_api.seam import Receipt, utc_now_iso  # noqa: E402

from schemas import SKILL_SCHEMAS  # noqa: E402

DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_BUDGET_USD = 0.50


def _content_sha256(structured_output: Any) -> str:
    """Content-address the skill's own answer: canonical (sorted-key) JSON, sha256 hex."""
    canonical = json.dumps(structured_output, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def invoke_skill(
    skill: str,
    prompt: str,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
    cwd: str | Path | None = None,
) -> Receipt:
    """Run one skill through claude-agent-sdk, force its schema, return a Receipt.

    `skills=[skill]` is a CONTEXT FILTER, not a guarantee of invocation (per the
    SDK's own docs: unlisted skills are hidden/rejected, but a listed one isn't
    forced to fire) -- the prompt still has to actually ask for the skill's work.
    Bounded by max_turns/max_budget_usd per the locked plan's Honest Cost #3:
    every node here is a full agentic session, not one inference.
    """
    if skill not in SKILL_SCHEMAS:
        raise ValueError(f"no output_format schema registered for skill {skill!r} "
                          f"(known: {sorted(SKILL_SCHEMAS)})")

    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        skills=[skill],
        setting_sources=["user", "project"],
        output_format={"type": "json_schema", "schema": SKILL_SCHEMAS[skill]},
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        cwd=str(cwd) if cwd else None,
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    produced_at = utc_now_iso()
    if result is None:
        return Receipt(tool=skill, sha256=None, produced_at=produced_at,
                        status="error", data=None, error="no ResultMessage received from the SDK")
    if result.is_error or result.structured_output is None:
        reason = result.result or "; ".join(result.errors or []) or "no structured_output returned"
        return Receipt(tool=skill, sha256=None, produced_at=produced_at,
                        status="error", data=None, error=reason)

    return Receipt(
        tool=skill,
        sha256=_content_sha256(result.structured_output),
        produced_at=produced_at,
        status="ok",
        data=result.structured_output,
        error=None,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="skill_nodes", description=__doc__.splitlines()[0])
    p.add_argument("skill", choices=sorted(SKILL_SCHEMAS))
    p.add_argument("prompt")
    p.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    p.add_argument("--max-budget", type=float, default=DEFAULT_MAX_BUDGET_USD)
    p.add_argument("--cwd", default=None)
    p.add_argument("--json", action="store_true", help="print the Receipt as JSON (default: human)")
    args = p.parse_args(argv)

    receipt = asyncio.run(invoke_skill(
        args.skill, args.prompt,
        max_turns=args.max_turns, max_budget_usd=args.max_budget, cwd=args.cwd,
    ))
    dumped = receipt.model_dump()
    if args.json:
        print(json.dumps(dumped, indent=2, sort_keys=True))
    else:
        print(f"{dumped['tool']}: {dumped['status']}"
              + (f" sha256={dumped['sha256'][:12]}..." if dumped["sha256"] else ""))
        if dumped["status"] == "error":
            print(f"  error: {dumped['error']}")
        else:
            print(json.dumps(dumped["data"], indent=2, sort_keys=True))
    return 0 if dumped["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
