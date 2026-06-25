# Session 3 kickoff · uasc-executor swap

Post-audit swap sequence · Session 3 of 4 · single swap, LOW risk.

## Invoke

Open a new Claude Code session rooted in `C:\Users\bruke\Pre Atlas` (or run `cd "C:\Users\bruke\Pre Atlas"; claude` in PowerShell). Paste the block below as the first message.

---

## Paste this as the first message

```
Session 3 of the post-audit swap sequence. One swap in services/uasc-executor. Risk: LOW.

LOAD CONTEXT FIRST:
1. audit/swap-backlog.md — Tier 2 row #7 is this session's scope
2. audit/swap-candidates.json — verdict + blockers for uasc-executor
3. audit/SESSION_2_KICKOFF.md — template (Session 2 shipped chunk_text + triage_server)
4. ~/.claude/rules/common/assemble-first.md — Atlas Law #2
5. ~/.claude/logs/session-retrospectives/pre-atlas/2026-05-29.md — read BOTH retros at the bottom (1a7b32e7 = Session 1, dd453321 = Session 2). Encode their lessons.

PRIOR SESSION SHAs (for chain-of-custody):
- Session 1: 3aa8093 (pino), 6680440 (lru-cache) — aegis-fabric plumbing
- Session 2: 2e6ef4a (chunk_text), 6328dc1 (triage_server) — cognitive-sensor
- HOLD: rate-limiter.ts (Tier 3 #17) — variable-per-tenant-quota model mismatch

LESSONS TO ENCODE FROM PRIOR SESSIONS:
- Session 1: audit verdicts are CATEGORY-level. Read public API + callsites BEFORE accepting GO. (Caught rate-limiter shape mismatch — flipped GO → HOLD.)
- Session 2a: `pip show <pkg>` BEFORE `pip install` to skip the 20-line "already satisfied" dep-resolution noise.
- Session 2b: FastAPI's `TestClient` is a cheap parity oracle for endpoint swaps — write the 8-10 line smoke (status codes + response body shapes) BEFORE the commit. Catches everything `pytest` misses when the test suite doesn't exercise the HTTP layer.
- Session 2c: When porting a stdlib http.server with daemon-thread fan-out, keep the threads sync — FastAPI runs sync handlers in starlette's threadpool, so the threading model is preserved with zero helper changes.

SCOPE (DO NOT EXCEED):
| # | File | From | To |
|---|---|---|---|
| 1 | services/uasc-executor/server.py L13 + L204-267 | raw `http.server.BaseHTTPRequestHandler` + manual JSON dispatch + HMAC auth check inline | fastapi (~64 handler LOC) + uvicorn |

NOT IN SCOPE:
- Session 4 xstate triple (delta-kernel + inPACT · doctrine-heavy · HIGH risk)
- Tier 3 HOLD revisits (rate-limiter, apscheduler, telegram→grammY, discord, memory.mjs)
- Tier 5 lattice patterns (tree/timeline/search)
- "While I'm in here" cleanups in other uasc-executor files
- Refactoring HMAC verification logic — port it intact

PRE-FLIGHT CHECKS (do these BEFORE any install):
1. `pip show fastapi uvicorn` to confirm Session 2's install carried over (Python 3.13.2 env — should be there already; skip install if so).
2. Read services/uasc-executor/server.py in full. Map: (a) the 4 endpoints, (b) the HMAC verification (which header? what's hashed? where's the secret loaded?), (c) any shared module state, (d) the entry-point / serve() function.
3. Find uasc-executor callers — grep for `from uasc-executor` and `uasc_executor`, check launch.json + .env files for ports, check ~/Pre Atlas/PRE_ATLAS_MAP.md for the port map (memory says :3008). What HITS those 4 endpoints? Any sibling service depend on the response shape?
4. Check for tests in services/uasc-executor/ — pytest? if none, the TestClient smoke is the ONLY parity check.

PER-SWAP WORKFLOW:
1. Read the swap-backlog.md row + swap-candidates.json entry
2. Read services/uasc-executor/server.py in full + the HMAC code path
3. Read 1-2 callsites (sibling services that hit /uasc/* or whatever the prefix is)
4. Propose the plan with explicit "same vs changes" table — especially the HMAC port shape (FastAPI Dependency? middleware? raw header check inside the handler?)
5. Pre-flight pip check; install only if missing
6. Make the swap — keep public URL paths + response shapes identical
7. TestClient smoke covering: each of 4 endpoints happy path, each with missing/bad HMAC, malformed JSON. Get these GREEN before commit.
8. Run any existing pytest suite
9. Show me the diff before committing
10. Commit: `refactor(uasc-executor): swap BaseHTTPRequestHandler → fastapi`
11. Update audit/swap-backlog.md — mark Tier 2 #7 ✓ SHIPPED with commit SHA

DEFINITION OF DONE for Session 3:
- [ ] 1 swap committed with conventional message
- [ ] Any existing uasc-executor tests pass
- [ ] TestClient smoke covers all 4 endpoints + HMAC failure paths (PASS)
- [ ] Public URL paths + response shapes unchanged (callers don't move)
- [ ] HMAC behavior byte-identical (same secret source, same hash construction, same 401/403 shape on failure)
- [ ] swap-backlog.md updated with ✓ + SHA
- [ ] Retro filled in at ~/.claude/logs/session-retrospectives/pre-atlas/<UTC-date>.md

CONTEXT BUDGET:
- LOW risk · single swap · should not exceed ~1.5 hrs / ~15% context
- Show the % bar per ~/.claude/rules/common/context-cadence.md
- Session 2 hit ~22% at done — Session 3 has less surface, should land closer to ~12-15%

KNOWN BLOCKERS (from Track 2D verification):
- HMAC auth middleware must be ported. Two FastAPI shapes work:
  (a) Dependency: `def verify_hmac(request: Request, x_signature: str = Header(...)): ...` injected per route — clean, per-route control
  (b) Middleware: `@app.middleware("http")` for cross-cutting — less explicit but no per-route boilerplate
  Pick (a) if HMAC isn't on EVERY route (i.e. health endpoint exempt). Pick (b) if it covers everything.
  Document the choice in the commit message.
- If HMAC reads `request.body()`, remember sync handlers can't await it — either use `async def` for those handlers OR use a Dependency that reads body via the Request object asynchronously then passes parsed shape downstream.

LAW #2 REMINDER:
This swap enforces "Assemble First."
- BaseHTTPRequestHandler + manual JSON dispatch in 2026 is a solved-category reinvention (same call as Session 2's triage_server).
- FastAPI's HMAC-via-Dependency pattern is canonical; the audit explicitly noted "HMAC middleware ports cleanly via FastAPI DI."
- The "worse vs later" test passes: a library does NOT make this worse. Moat budget freed goes to xstate doctrine work in Session 4.

WHEN DONE:
Reply with: commit SHA, test pass count, TestClient smoke summary, HMAC port shape chosen (Dependency vs Middleware), and a one-line note on whether Session 4 (xstate triple, HIGH risk, DOCTRINE) is ready to plan or needs its own dedicated planning session first.

Start by reading audit/swap-backlog.md (Tier 2 #7) + swap-candidates.json (uasc-executor entry) + both 2026-05-29 retros (Sessions 1 + 2). Then run the PRE-FLIGHT CHECKS before proposing any plan.
```

---

## After Session 3

Next file: `audit/SESSION_4_KICKOFF.md` — and this one needs a dedicated planning session BEFORE the kickoff is written. Session 4 is the xstate triple (delta-kernel Mode FSM + inPACT onboarding goStep + inPACT screens.js stateManager) — these are doctrine, not plumbing. The kickoff template won't be enough; the FSM semantics need a design pass first.

## Sequence ahead (for tracking)

| Session | Service | Swaps | Risk | Status |
|---|---|---|---|---|
| 1 | aegis-fabric | pino + lru-cache + (rate-limiter HOLD) | low | ✅ SHIPPED |
| 2 | cognitive-sensor | langchain-text-splitters + fastapi (triage_server) | medium | ✅ SHIPPED |
| **3 · THIS ONE** | uasc-executor | fastapi (server.py) | **LOW** | ⬜ pending |
| 4 | delta-kernel + inPACT ×2 | xstate triple | **HIGH — doctrine, plan first** | ⬜ planning-needed |
