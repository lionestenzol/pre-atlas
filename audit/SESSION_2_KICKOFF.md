# Session 2 kickoff · cognitive-sensor swaps

Post-audit swap sequence · Session 2 of 4 · text-chunking dedup + FastAPI lift.

Risk: MEDIUM (FastAPI async/threading boundary in triage_server). Session 1 was plumbing; this one has shape.

## Invoke

Open a new Claude Code session rooted in `C:\Users\bruke\Pre Atlas` (or run `cd "C:\Users\bruke\Pre Atlas"; claude` in PowerShell). Paste the block below as the first message.

---

## Paste this as the first message

```
Session 2 of the post-audit swap sequence. Two swaps in services/cognitive-sensor. Risk: MEDIUM.

LOAD CONTEXT FIRST:
1. audit/swap-backlog.md — Tier 2 rows #6 and #9 are this session's scope
2. audit/swap-candidates.json — verdicts + blockers for each
3. audit/SESSION_1_KICKOFF.md — reference template + 2 SHAs landed (3aa8093 pino, 6680440 lru-cache)
4. ~/.claude/rules/common/assemble-first.md — Atlas Law #2
5. ~/.claude/logs/session-retrospectives/pre-atlas/2026-05-29.md — session_id 1a7b32e7-* "What to do better" bullets (especially: read callsites BEFORE proposing the plan; check git tracking BEFORE editing)

SESSION 1 LESSON (encode in workflow):
The audit's GO/HOLD verdicts are category-level. Always read the actual public API + callsites BEFORE accepting GO. Session 1 caught a GO→HOLD flip on rate-limiter because the hand-roll took quota PER CALL while rate-limiter-flexible takes points at CONSTRUCTION. That kind of shape mismatch only shows up in the source, not the audit.

SCOPE (DO NOT EXCEED):
| # | File | From | To |
|---|---|---|---|
| 1 | services/cognitive-sensor/agent_excavator.py L142-155 + services/cognitive-sensor/agent_book_miner.py L196-209 | hand-rolled `chunk_text()` (identical duplicate, 2×14 LOC) | langchain-text-splitters · RecursiveCharacterTextSplitter |
| 2 | services/cognitive-sensor/triage_server.py L23 + L120-197 | raw `http.server.BaseHTTPRequestHandler` + TriageHandler background-thread | fastapi (~77 handler LOC) |

NOT IN SCOPE:
- Tier 1 xstate swaps (Session 4, doctrine-heavy)
- Other Tier 2 swaps (Session 3 = uasc-executor)
- Refactoring callsites beyond what the swap requires
- "While I'm in here" cleanups in other cognitive-sensor files
- Lattice UI work (separate thread, not part of swap sequence)

PRE-FLIGHT CHECKS (do these BEFORE any install):
1. `python --version` in the cognitive-sensor venv. langchain-text-splitters requires Python >=3.10. If venv is older, STOP and surface — don't auto-upgrade.
2. Read both chunk_text() implementations side-by-side. Confirm they are byte-identical word-boundary chunkers (audit claims they are; verify).
3. Read triage_server.py in full. Identify EVERY callsite that touches the threading model (TriageHandler.handle_*, any background-thread spawn, any shared mutable state). The async boundary is the risk; map it before proposing the swap.
4. Find triage_server callsites — what starts the server? what hits its endpoints? Anything depend on the threading model externally?

PER-SWAP WORKFLOW (sequential, one at a time):
1. Read the swap-backlog.md row + swap-candidates.json entry
2. Read the target file in full
3. Read 2-3 callsites to understand the public API to preserve (THIS IS THE SESSION 1 LESSON)
4. Propose the plan with explicit "what's the same vs what changes" table
5. Install the lib (pip via the cognitive-sensor venv — confirm path first)
6. Make the swap — keep the public API identical so callers don't change (or surface the call-shape change with a precise list of touched callsites)
7. Run tests — find the cognitive-sensor test command (likely `pytest` or a script in cognitive-sensor/)
8. Show me the diff before committing
9. Commit: `refactor(cognitive-sensor): swap <hand-roll> → <library>`
10. Update audit/swap-backlog.md — mark Tier 2 #N ✓ SHIPPED with commit SHA

DEFINITION OF DONE for Session 2:
- [ ] Both swaps committed with conventional messages (or 1 swap + 1 documented HOLD if a blocker surfaces in callsite read)
- [ ] All cognitive-sensor tests pass
- [ ] Public API of chunk_text + triage_server endpoints unchanged (callers/callers-of-endpoints don't move)
- [ ] swap-backlog.md updated with ✓ + SHA per row
- [ ] Retro filled in for this session at ~/.claude/logs/session-retrospectives/pre-atlas/<UTC-date>.md
- [ ] If FastAPI swap is HOLD, document the specific reason (e.g., threading boundary too entangled, missing test coverage) — Session 1's rate-limiter HOLD is the template

CONTEXT BUDGET:
- This is MEDIUM risk — should not exceed ~2.5 hrs
- Show the % bar per ~/.claude/rules/common/context-cadence.md
- If you hit 25% before swap 2, COMMIT what's done, write tight handoff for Session 2b, PARK
- FastAPI swap is the bigger lift; consider doing the chunker swap FIRST (cleaner win, lower risk) so the session ships something even if FastAPI ends up HOLD

KNOWN BLOCKERS (from Track 2D verification):
- chunk_text: Python >=3.10 required. Confirm before pip install. If runtime is 3.9 or older, do NOT silently bump — surface to user.
- triage_server fastapi: TriageHandler uses background-thread sync model. FastAPI is async-first. Options when you get there:
  (a) BackgroundTasks for fire-and-forget work
  (b) starlette.concurrency.run_in_threadpool for blocking calls
  (c) Keep the worker in a thread, expose only the HTTP layer via FastAPI
  Pick the option that requires the FEWEST callsite changes. Encode the decision in the commit message.

LAW #2 REMINDER:
These swaps enforce "Assemble First."
- chunk_text duplicate (2× 14 LOC across files) is textbook drift risk — one PR removes both.
- BaseHTTPRequestHandler + manual JSON dispatch in 2026 is a solved-category reinvention.
The "worse vs later" test: a library does NOT make these worse here. Moat budget freed = reinvested in cognitive-sensor's actual moat (LSH/embeddings/clustering — already correctly assembled, see swap-backlog.md "What was already correctly assembled").

WHEN DONE:
Reply with: commit SHAs, test pass count, any caveat (especially around the FastAPI swap if it landed). Then ask whether to start Session 3 (uasc-executor · LOW risk) or park.

Start by reading audit/swap-backlog.md (Tier 2 #6 + #9 rows) + the matching swap-candidates.json entries + ~/.claude/logs/session-retrospectives/pre-atlas/2026-05-29.md (1a7b32e7 retro). Then run the PRE-FLIGHT CHECKS list before proposing any plan.
```

---

## After Session 2

Next file: `audit/SESSION_3_KICKOFF.md` (to be written when Session 2 closes). Same shape, uasc-executor fastapi swap (LOW risk, 4 endpoints, HMAC middleware needs port).

## Sequence ahead (for tracking)

| Session | Service | Swaps | Risk | Status |
|---|---|---|---|---|
| 1 | aegis-fabric | pino + lru-cache + (rate-limiter HOLD) | low | ✅ shipped 2026-05-29 · `3aa8093` `6680440` |
| **2 · THIS ONE** | cognitive-sensor | langchain-text-splitters + fastapi (triage_server) | medium (async boundary) | ⬜ pending |
| 3 | uasc-executor | fastapi (server.py · 4 endpoints) | low | ⬜ pending |
| 4 | delta-kernel + inPACT ×2 | xstate triple | **HIGH — doctrine** | ⬜ pending |

## What changed since Session 1

- `audit/swap-backlog.md` updated: Tier 2 #4, #5 ✓ shipped; #8 demoted to Tier 3 #17 HOLD
- `audit/swap-candidates.json` updated: rate-limiter verdict GO → HOLD with original_verdict_at_audit field added
- All previously-untracked audit/ files now committed (`39f89ef`)
- Lattice UI work happened in parallel sessions (apps/lattice/index.html · graph toolbar / mode switching) — that's a separate thread, not part of the swap sequence and out of scope here.
