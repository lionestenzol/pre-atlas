# Session 1 kickoff · aegis-fabric swaps

Post-audit swap sequence · Session 1 of 4 · plumbing only (no doctrine touch).

## Invoke

Open a new Claude Code session rooted in `C:\Users\bruke\Pre Atlas` (or run `cd "C:\Users\bruke\Pre Atlas"; claude` in PowerShell). Paste the block below as the first message.

---

## Paste this as the first message

```
Session 1 of the post-audit swap sequence. Three swaps in services/aegis-fabric. No doctrine touch. Sequential, not parallel.

LOAD CONTEXT FIRST:
1. audit/swap-backlog.md — Tier 2 rows #4, #5, #8 are this session's scope
2. audit/swap-candidates.json — verdicts + blockers for each
3. ~/.claude/rules/common/assemble-first.md — the rule that named these
4. services/cognitive-sensor/ATLAS_LAWS.md — Law #2 (what these swaps enforce)

SCOPE (DO NOT EXCEED):
| # | File | From | To |
|---|---|---|---|
| 1 | services/aegis-fabric/src/observability/logger.ts | hand-rolled JSON logger (48 LOC) | pino v10 |
| 2 | services/aegis-fabric/src/policies/decision-cache.ts | hand-rolled LRU + TTL (63 LOC) | lru-cache v11 (native TTL) |
| 3 | services/aegis-fabric/src/gateway/rate-limiter.ts | hand-rolled token-bucket (65 LOC) | rate-limiter-flexible v11 |

NOT IN SCOPE:
- Tier 1 xstate swaps (Session 4, doctrine-heavy)
- Other Tier 2 swaps (Sessions 2 + 3)
- Refactoring callsites beyond what the swap requires
- "While I'm in here" cleanups in other aegis-fabric files

PER-SWAP WORKFLOW (sequential, one at a time):
1. Read the swap-backlog.md row + swap-candidates.json entry
2. Read the target file in full
3. Read 1-2 callsites to understand the public API to preserve
4. Install the lib (check services/aegis-fabric/package.json for the right pkg mgr)
5. Make the swap — keep the public API identical so callers don't change
6. Run tests — cd services/aegis-fabric && <test command from package.json>
7. Show me the diff before committing
8. Commit: `refactor(aegis-fabric): swap <hand-roll> → <library>`
9. Update audit/swap-backlog.md — mark Tier 2 #N ✓ SHIPPED with commit SHA

DEFINITION OF DONE for Session 1:
- [ ] 3 swaps committed with conventional messages
- [ ] All aegis-fabric tests pass
- [ ] Public API of logger/cache/rate-limiter unchanged (callers don't move)
- [ ] swap-backlog.md updated with ✓ + SHA per row
- [ ] Brief retro filled in for this session

CONTEXT BUDGET:
- This is plumbing — should not exceed ~2 hrs
- Show the % bar per ~/.claude/rules/common/context-cadence.md
- If you hit 25% before swap 3, COMMIT what's done, write tight handoff for Session 1b, PARK

KNOWN BLOCKERS (from Track 2D verification):
- logger.ts: pino handles child loggers + redaction natively — check API parity for any context-attach helpers
- decision-cache.ts: lru-cache v11 has `ttl`, `ttlAutopurge`, `maxSize` — map carefully to hand-roll's eviction policy
- rate-limiter.ts: rate-limiter-flexible supports composite keys via constructor — port the key fn intact

LAW #2 REMINDER:
These swaps enforce "Assemble First." The "worse vs later" test passes for all three: a library does NOT make these worse, just earlier-completed and shifted onto upstream maintenance. Moat budget freed = reinvested in delta-kernel / signal-mapping / PNG-substrate.

WHEN DONE:
Reply with: 3 commit SHAs, test pass count, any caveat before merging. Then ask whether to start Session 2 (cognitive-sensor) or park.

Start by reading audit/swap-backlog.md (Tier 2 #4 row) and the matching swap-candidates.json entry. Then propose your plan for swap #1 (pino) before touching code.
```

---

## After Session 1

Next file: `audit/SESSION_2_KICKOFF.md` (to be written when Session 1 closes). Same shape, swapping in cognitive-sensor's two candidates.

## Sequence ahead (for tracking)

| Session | Service | Swaps | Risk |
|---|---|---|---|
| **1 · THIS ONE** | aegis-fabric | pino + lru-cache + rate-limiter-flexible | low (plumbing) |
| 2 | cognitive-sensor | langchain-text-splitters + fastapi (triage_server) | medium (FastAPI async boundary) |
| 3 | uasc-executor | fastapi (server.py) | low (4 endpoints) |
| 4 | delta-kernel + inPACT ×2 | xstate triple | **HIGH — doctrine** |
