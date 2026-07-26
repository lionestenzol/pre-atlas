# Next-session kickoff prompt

**→ NEXT LIVE PROMPT: [audit/SESSION_1_KICKOFF.md](SESSION_1_KICKOFF.md)** (aegis-fabric · 3 plumbing swaps · pino + lru-cache + rate-limiter-flexible).

---

**STATUS · COMPLETED 2026-05-29 (later session, same day).** All four deferred phases shipped:

- ✅ Track 2A → [audit/reinvention-surface.json](reinvention-surface.json) — sequential Sonnet walk, 8 verified candidates across 4 services, 6 clean subsystems
- ✅ Track 2D → [audit/swap-candidates.json](swap-candidates.json) — 14 candidates verified · 7 GO / 4 HOLD / 3 SKIP
- ✅ [audit/swap-backlog.md](swap-backlog.md) — expanded into 5 tiers, Top 3 NEXT-SHIP unchanged, 6 new GO swaps added
- ✅ [audit/moat-map.md](moat-map.md) — crucix LLM factory promoted to confirmed moat (9-provider abstraction; no Node.js peer to litellm with Ollama coverage)

Atlas Law #2 (Assemble First) is already live in `services/cognitive-sensor/ATLAS_LAWS.md`. No further chips queued.

---

## Historical record (original kickoff text below)

Pre Atlas dogfood audit · resume after partial completion 2026-05-29.

## Invoke

Open a new Claude Code session rooted in `C:\Users\bruke\Pre Atlas` (or run `cd "C:\Users\bruke\Pre Atlas"; claude` in PowerShell).

## Paste this as the first message

```
Continue the Pre Atlas dogfood audit. Plan file: ~/.claude/plans/youre-guessing-you-dot-enumerated-whistle.md.

DONE in prior session (artifacts on disk):
- Phases 0, 1, 2B (Gemini lava-layers), 2C (vocab-collisions) — see audit/
- 5 deliverables shipped: assemble-first.md (global rule), swap-backlog.md (PARTIAL), moat-map.md, user_engineering_fingerprint.md, development-workflow.md step 0 updated

FAILED in prior session:
- Track 2A (systematic per-service reinvention scan). 6 Haiku agents thrashed on context. None wrote JSON. Two hallucinated file paths.
- Track 2D (ecosystem prior-art). Never ran — depended on 2A.

YOUR JOB: complete 2A + 2D, then update D2 (swap-backlog).

Strategy that should work:
1. ONE Sonnet agent, sequential walk (NOT parallel fanout — that's what broke). Service order: cognitive-sensor → aegis-fabric → canvas-engine → cortex → optogon → code-converter → uasc-executor → perception → triangulation → crucix → ws-gateway. Skip the 6 retired services (mirofish, openclaw, mosaic-orchestrator, blueprint-generator, mosaic-dashboard, ai-exec-pipeline — see audit/lava-layers.json).
2. Per service: hand-roll candidates in solved categories (full list in ~/.claude/rules/common/assemble-first.md). VERIFY against actual source (no hallucinated paths). Per candidate emit: file, library_canonical, library_alts, confidence_swap_safe, moat_risk. Append to audit/reinvention-surface.json.
3. Then one Sonnet agent + WebSearch + `gh search repos` does Track 2D: for each candidate, confirm canonical library, check it existed at the subsystem's epoch (cross-ref audit/lava-layers.json), note maintenance metrics. Output audit/swap-candidates.json.
4. Edit audit/swap-backlog.md to add verified candidates with priority scores. Edit audit/moat-map.md if surprises reveal new moats.

ALREADY-CONFIRMED candidates (do not re-audit): delta-kernel Mode FSM (xstate), inPACT onboarding goStep (xstate/felte), inPACT screens.js state (xstate). These are in D2's Top 3 NEXT-SHIP. Only audit OTHER services for OTHER categories.

Context discipline: don't read audit/system-index.json or audit/lava-layers.json into your own context — let the agents consume them. Use summarizer agents if outputs >100 lines.

Start by reading audit/swap-backlog.md (gap section explains what's missing) and audit/system-shape.md (29 subsystems + Phase 1 spot-checks), then plan the 2A sequential walk.
```

## State summary (for human scanning)

| Artifact | Status |
|---|---|
| `audit/reuse-map.md` | ✅ Phase 0 — existing inventory reconciled |
| `audit/system-index.json` + `audit/system-shape.md` | ✅ Phase 1 — 29 subsystems mapped |
| `audit/lava-layers.json` | ✅ Phase 2B — Gemini-produced temporal map, 22 subsystems |
| `audit/vocab-collisions.json` | ✅ Phase 2C — 11/12 high-severity, `engine`=9 meanings |
| `audit/reinvention-surface.json` | ❌ Phase 2A — Haiku fanout failed, **NOT WRITTEN** |
| `audit/swap-candidates.json` | ❌ Phase 2D — never ran |
| `audit/swap-backlog.md` | ⚠️ Phase 3 — **PARTIAL** (3 confirmed + 7 likely, needs expansion from 2A/2D) |
| `audit/moat-map.md` | ✅ Phase 3 |
| `~/.claude/rules/common/assemble-first.md` | ✅ Phase 3 — global rule live |
| `~/.claude/rules/common/development-workflow.md` | ✅ Phase 3 — Step 0 updated |
| `~/.claude/projects/.../memory/user_engineering_fingerprint.md` | ✅ Phase 3 |

Chip queued in prior session: "Add Atlas Law #2: Assemble First" to `services/cognitive-sensor/ATLAS_LAWS.md` (Law #1 is TGT).
