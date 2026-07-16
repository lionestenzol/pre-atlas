# lattice — Skill → Receipt adapters (LangGraph Skill Lattice, Seq 2)

Wraps a genuinely agentic Claude Code Skill invocation (`claude-agent-sdk`, `skills=[...]`,
forced `output_format`) into the same `seam.v1` Receipt shape every deterministic tool in
this stack already produces — so a downstream LangGraph node (Seq 3) can treat an LLM-driven
skill call and a plain CLI call identically.

## Why only 3 skills

The locked plan (`docs/LANGGRAPH_SKILL_LATTICE_PLAN.md`) named ~8 skills by ledger volume.
Checking each one's actual determinism narrowed that to the 3 that genuinely need an LLM
invocation to produce their answer — the rest already have a zero-LLM Receipt path (Seq 1's
`/seam/call`, or are explicit non-goals). See `schemas.py`'s module docstring for the
skill-by-skill reasoning.

| Skill | Needs this adapter? | Why |
|---|---|---|
| **code-recon** | ✅ | Genuine reasoning to search/cite/conclude. Explicit 7-section output contract. |
| **groundwork** | ✅ | Genuine reasoning to pick regions, interpret evidence, author a plan. |
| **weapon** | ✅ | Genuine reasoning to spec/plan/execute/close. Explicit closed.md contract. |
| delta-scp | ❌ | Already reachable via `/seam/call` — zero-LLM HTTP surface. |
| repo-inventory | ❌ | Already reachable via `/seam/call` — zero-LLM CLI surface. |
| bearings | ❌ | Skill's own SKILL.md: "Zero LLM. Zero agents." Wrapping it would waste a real session. |
| fest | ❌ | Plan's own NON-GOALS: LangGraph shouldn't reach fest's Go internals; status/list/progress are plain CLI. |
| seam | ❌ | It's the dispatcher — its own Receipts already ARE seam.v1 shaped. |

## Use

```bash
python skill_nodes.py code-recon "locate where run_id is threaded through /seam/call" --json
python skill_nodes.py weapon "close out the chatpull archive skill" --max-budget 1.00
```

Bounded by `--max-turns` (default 12) and `--max-budget` (default $0.50 USD) — every call
here is a full Claude agentic session, not one inference (Honest Cost #3 in the plan).

## Caveat: `skills=[...]` is a filter, not a guarantee

`claude-agent-sdk`'s own docs are more precise than the plan's shorthand ("forces a named
skill"): `skills=[...]` is a **context filter** — it hides/rejects every *other* skill from
the model's listing, but does not itself force the named one to fire. The prompt still has
to actually ask for the work that skill does. Verified directly against the installed SDK
(0.2.120) on 2026-07-16 — see `ClaudeAgentOptions.skills`'s docstring in
`claude_agent_sdk/types.py`.

## Receipt shape

Same `seam.v1` Receipt as everything else (`atlas_map_api.seam.Receipt`): `tool`, `sha256`,
`produced_at`, `status`, `data`, `error`. The one difference from a CLI-wrapped tool: there's
no tool-printed sha256 to lift, so `sha256` here is computed locally — the content-address of
the skill's own `structured_output` (sorted-key canonical JSON, sha256 hex), not of an input
file. Two runs that produce byte-identical structured output get the same sha256; that's the
idempotency key Seq 3's `@task` wrapping will rely on.
