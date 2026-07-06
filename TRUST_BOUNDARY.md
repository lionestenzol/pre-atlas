# Trust boundary

One rule, derived from why Atlas, ATM, and UASC all strip self-expansion at ship time — see [ATLAS_ATM_UASC_ANALYSIS.md](ATLAS_ATM_UASC_ANALYSIS.md) §3.

## The rule

**Capability and trust change only by source-diff + redeploy. Never by a runtime request, proposal, or payload — no matter how many review steps sit in between.**

Anything derived from live or untrusted content — sensor input, tool output, web content, an AI-generated proposal — must never reach the action surface. Not "reviewed before it reaches." Not "staged then approved." Unreachable, period.

## Why a review gate doesn't satisfy this

A staged-proposal-plus-review-gate protects determinism and auditability. It does not protect against injection, because the reviewer becomes the new target. An automated reviewer is exactly as attackable as the model that produced the proposal. A human reviewer is exactly what sophisticated injection is built to slip past — a payload buried in something that reads as benign, or plain review fatigue on the fiftieth auto-generated approval. And one bad approval doesn't fail once; it persists as a real, registered capability until someone notices and revokes it.

The only version of this that actually holds: the proposal path is architecturally unreachable from anything that also processes untrusted content. Not defended against. Absent.

## The test

Run any new capability, glyph, action type, or automation through this before building it:

1. **Can the system change what it's allowed to DO from something it merely observed?** Yes → stop. This is the self-expansion surface, not a feature request.
2. **Does the change require a person to write code, commit it, and redeploy?** No → it isn't safe yet, no matter how many gates sit in front of it.
3. **If the mechanism involves learning or distillation from live data** (e.g. Federated Distillation): does its output ever influence the action surface? Adapting predictions, routing, or compression — fine. Registering, approving, or unlocking a new action, token, or ExecutionGraph — never.

## Verified status (2026-07-06)

| Surface | Status | Evidence |
|---|---|---|
| Atlas / delta-kernel `ActionType` | closed by source | `services/delta-kernel/src/core/types-core.ts:263-270` — 7 fixed strings. Enforced at execution by `isActionAllowedInMode` (`cockpit.ts:128`), checked at both `POST /api/actions/confirm/:id` and `workController.claimNextExecutable` (commit `348788b`). |
| UASC shipped service (`uasc-executor`, :3008) | closed by source | 10 tokens seeded once in `services/uasc-executor/storage/schema.sql:55-65`. `server.py` exposes 4 routes, none of which insert new commands. Unknown `cmd` 404s (`server.py:138`). |
| UASC lab reference impl (`research/uasc-m2m/reference-implementation/core/registry.py`) | open, not a live risk today | `Registry.register_graph()` (`:99`) and `.bind_glyph()` (`:113`) are live callable methods, no compile/runtime separation. Not wired to anything running. **Do not expose this over an API or let an agent call it without retrofitting the closed-by-source guarantee first.** |
| ATM transport/learning layer | undesigned, not built | Zero code exists — `data-mule`/`sundial`/`federated` all absent outside the brainstorm doc. The design calls for Federated Distillation: nodes adapting from live data. If this is ever built, the wall (learning changes predictions, never actions) has to be drawn before the first line of code, not retrofitted after. |
| delta-scp as ATM's seed engine (proposed, unbuilt) | pending | Depends entirely on whether its output stays read-only or becomes executable. Not yet decided. |

## Applying this to something new

Run it through the test above. If it fails step 1, it isn't a feature request — it's a request to reopen a surface every shipped system in this repo has deliberately closed. Say so and stop, rather than designing a gate around it.
