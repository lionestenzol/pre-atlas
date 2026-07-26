# ATLAS MASTER PLAN — The Pivot to Peak
**Date:** 2026-07-07 · **Status:** LIVE DOC (supersedes prior strategy snapshots; this is the front-door plan)
**Companion festival:** `C:\Users\bruke\festival-project\festivals\planning\atlas-pivot\`
**Evidence base:** completeness audit 07-06, potential audit 07-07, machine-substrate recon 07-07, live/dead census 07-07 — all claims file:line cited, load-bearing claims spot-verified first-hand at HEAD `8baf31f`.

---

## Part I — The Diagnosis: why a living graveyard

Atlas was built as an execution prosthetic for one high-intelligence, high-velocity individual, out of internalized paper processes. It is now **referred to, thought through, but not lived through** — a background oracle instead of a foreground prosthetic. The census confirms both halves of "living graveyard":

**Alive (verified 2026-07-07):** 13 live services, 6 enabled Windows scheduled tasks, a work queue with **53 completed jobs** in its ledger (`services/cognitive-sensor/work_ledger.json`, verified by direct read — a prior report undercounted it at 4), a describe/call gateway exposing 74 capabilities across 10 surfaces, signed append-only deltas, content-addressed seam receipts, and — as of 72 hours ago — a proactive push spine (06:00 seeded day, pending-action confirms, task-completion pushes).

**Dead or dark:** 2 superseded apps (blueprint-generator — *still launched by `start_atlas.ps1` line 25* — and ai-exec-pipeline), 3 services in `_retired/`, 3 dormant apps, ~50 of 67 root .md files as dated snapshots, `research/uasc-m2m` quarantined, ws-gateway skipped (port collision with lattice on :3011, needs NATS broker), and — critically — **two load-bearing services built but not running**: memory-hub :3071 (the "ask my history" API over 6,534 conversations / 258,777 embeddings) and atlas-map-api :3072 (the items backbone + freshest map). Verified dark by port check this session.

**The disease has one name: the write-back gap.** Work happens; state doesn't update; the governor punishes. The proof is the mode-lock: Atlas sits in CLOSURE / `build_allowed: false` not because of discipline but because of **three stacked ledger bugs** (potential audit §2, all verified):

- **Bug A** — `closure_quality` is an all-time ratio (`cognitive_api.py:36-45`) poisoned by 145 bulk-ARCHIVE rows from one night (2026-06-21). Reaching the 30% unlock threshold (`atlas_config.py:340`) requires 63 consecutive CLOSE decisions. **Mathematically unrecoverable as built.**
- **Bug B** — the governor's own recommended command (`atlas-ai close`) hits `/api/law/close_loop` (`server.ts:1253-1443`), which never writes the `loop_decisions` table the metric reads. Obeying the system verbatim leaves the metric at 0 forever.
- **Bug C** — three loop lists with two id-generations disagree; but 12 of 15 governor-counted loops already have completed extraction docs in `services/cognitive-sensor/extractions/` — the closing work was done, the decision row never written.

This is the graveyard mechanism in miniature: **the system demands executive function from the person it exists to prosthetize, then punishes him with its own bookkeeping bugs.** Every campaign below exists to invert that.

---

## Part II — The Grand Strategy: one substrate, two beneficiaries

Your instinct — "this would be better for machines" — is not a pivot away from the human prosthetic. It is **how the human prosthetic finally works.** Already true today: you are not the executor (operating profile: every action runs through Claude/agents). The 2026-07-04 vision memory already named it: *Atlas IS the execution substrate; agents are the actors; the mode ladder becomes a system-health throttle; aegis gates become standard runtime guardrails.*

So the convergence thesis:

> **The machine substrate does the executing. The human interface shrinks to three touchpoints: the morning push, the one-tap decision, and the REQUIRE_HUMAN approval.** Everything else is agents claiming work from a governed queue and leaving receipts.

That is what "compounding, exponential, asymmetric leverage" means concretely here: your input is *decisions* (seconds), the system's output is *executed work* (hours), and the ledger compounds trust so the auto tier widens over time — but the capability set never widens at runtime.

### The Laws (the doctrine that governs every move)

1. **Law of the Closed Set.** Capabilities change only by source-diff + redeploy — never by runtime request, no matter how many review gates sit in between (`TRUST_BOUNDARY.md`; `ActionType` closed union `types-core.ts:263-270`, enforced `cockpit.ts:128`; UASC's 10 tokens seeded only in `schema.sql:55-65`). Fleet growth = more *tenants/tokens* (data), never more *verbs* (code).
2. **Law of Push, Not Pull.** The prosthetic speaks first. Any feature whose first step is "Bruke remembers to ask" is mis-shaped. The 06:00 seeded-day push (`governance_daemon.ts:149,464-528`) is the reference shape; everything rides that spine.
3. **Law of the Recorded Decision.** Work is not done until the ledger row exists. Bug B is what happens otherwise. Every close, kill, ship, and skip writes to the table the governor reads.
4. **Law of One Tap.** Every human touchpoint is a decision executable in ≤2 minutes (Atomic Habits' two-minute rule). If it takes longer, it is agent work wearing a human costume — re-route it to the queue.
5. **Law of Assembly.** Nothing gets built while a dormant equivalent exists. memory-hub, the tenant routes, NATS, triangulation are all built-and-dark; on-switches before new code, always.
6. **Law of the Single Front Door.** One entry (CLAUDE.md → atlas-map MCP → atlas-ai CLI → REST), one live plan (this doc), <10 live root docs. Duplicated maps are how agents and humans get lost in the graveyard.
7. **Law of the Permanent Partner.** REQUIRE_HUMAN on high-blast-radius actions is a design constant, not training wheels (vision memory, Bruke's explicit correction). Autonomy grows *around* that gate, never through it.
8. **Law of the Paced Substrate.** The mode ladder (RECOVER→…→SCALE) survives the pivot re-purposed: it throttles *system concurrency and risk tier*, and separately protects *the human's* attention budget. Two governors, one ladder.

---

## Part III — The Campaigns (start to finish)

Ordered; each unlocks the next. Effort labels are honest. Full proof-gated task breakdown lives in the fest festival; this is the command view.

### Campaign 0 — UNLOCK (Day 1, ~2-3 hours) · *"Answer the governor"*
The gate for everything. Nothing else starts while `build_allowed: false`.
1. Fix Bug A: window `closure_quality` (last-30-days or exclude the 06-21 bulk rows as a `TRIAGE` decision type) — `cognitive_api.py:36-45`.
2. Fix Bug B: one INSERT — `/api/law/close_loop` also writes `loop_decisions` (`server.ts:1253-1443`). Two ledgers become one truth.
3. Run the drain with `loop_clearer.py` (shipped `54206ef`): **CLOSE loop 5272** ("AI Workflow Orchestration", 488 days — the repo itself is its artifact; extraction doc already says CLOSED); **kill loop 3411** (CUBECORE64 — zero artifacts anywhere, recorded as CLOSE-with-kill, never ARCHIVE); use the 12 existing extraction docs as ready-made closure artifacts for the rest.
4. Doc archive: `git mv` ~50 dated root snapshots → `docs/archive/2026-XX/` (pattern already established by `6e8992e`). Root keeps <10 live docs.
**Exit criterion (provable):** `atlas-ai state` shows mode ≠ CLOSURE, `build_allowed: true`, drift alerts cleared.

### Campaign I — RITUAL (Week 1) · *"Atomic Habits, mechanized"*
Point the 72-hour-old push spine at the goldmine. The habit loop, mapped to infrastructure:

| Habit law | Mechanism |
|---|---|
| Cue (make it obvious) | Pushes arrive at fixed times: 05:45 sensor → 06:00 seeded day → evening wrap. You never initiate. |
| Craving (make it attractive) | The push carries *your own* best material: one Execute-Now idea (of 1,335 ranked, currently zero delivery) + one open loop with its extraction summary. |
| Response (make it easy) | One tap: the pending-action confirm path (`f6a0c61`/`4e12bfe`, openclaw `/approve` + inPACT banner) already does one-tap decisions — reuse, don't build. |
| Reward (make it satisfying) | The tap writes the ledger row (Bug B fixed) → metric visibly moves → streaks/mode respond → evening push echoes wins. |

Moves: extend `seedTodayPlan` (+idea, +loop, one-tap close); evening wins push (`MomentumWins` currently has **zero consumers** — `atlas-ai.ts:430-438`); RECOVER/low-energy mornings seed a *lighter* day + one past win instead of a full load (RECOVER is currently a label only, `atlas-ai.ts:513-520`). Hard cap on push volume — the ritual is a heartbeat, not a nag; inPACT-as-harassment is the failure mode this replaces.
**Exit criterion:** 7 consecutive days where the day arrives seeded with idea+loop, ≥1 one-tap decision recorded per day, evening wrap fires.

### Campaign II — LIGHTS ON (Week 1, parallel with I, mostly on-switches) · *"Wake the dormant load-bearers"*
1. Autostart memory-hub :3071 + atlas-map-api :3072 (add to `start_atlas.ps1` / launch config). This lights up: ask-my-history (`POST /search` over the 6,534-conversation corpus — the digital-twin v1), the items backbone (`server.py:507,520,546`), and the freshest map.
2. Schedule `atlas_reload` after the nightly manifest regen — the front door stops serving a 13-day-old map.
3. Remove blueprint-generator from `start_atlas.ps1:25` (superseded by canvas-engine per `lava-layers.json`; census-confirmed dead).
**Exit criterion:** :3071/:3072 up after reboot; `atlas_call(memory-hub, search)` returns results; map `generated_at` < 24h old.

### Campaign III — SUBSTRATE (Weeks 2-3) · *"From one agent to a fleet"*
The machine-pivot proper. Recon verdict: *"instrumented well for ONE agent, not architected for fleets."* Gateway READY, receipts READY, work queue PARTIAL, tenancy DARK, onboarding MISSING. Four moves, all within the Closed Set:
1. **The contract:** write `AGENT_SUBSTRATE.md` — the machine-onboarding quickstart (token bootstrap → `atlas_describe_list()` → `atlas_call` → work claim/heartbeat/complete loop). Today an external agent must reverse-engineer this from source. DoD: a fresh agent session completes a full claim→complete cycle *following only the doc*.
2. **Identity & tenancy:** thread `agent_id` through the work queue (claims, ledger attribution — `claimed_by` field already exists); generalize `ATLAS_USER_ID` (`server.ts:53`, env-overridable already); provision scoped agent keys through aegis-fabric's **already-built** tenant routes (`tenant-routes.ts:14-24` returns `tenant_id` + `api_key` — dark, not missing). UASC client registration gets a documented (human-executed, source-side) onboarding path — *not* a runtime self-registration API (Law 1).
3. **Events over polling:** work availability today requires poll loops. NATS emission already exists with graceful degradation (`event-emitter.ts`; `task.completed` at `work-controller.ts:710`). Decide once: stand up the NATS broker + ws-gateway (now on :3013, its :3011/lattice collision fixed 2026-07-15) *or* add an SSE `/api/work/subscribe`. Either ends polling.
4. **Retry doctrine:** expired claims currently die as `failed` with no re-queue (`work-controller.ts:1004`); define supervisor-level retry (bounded attempts — the `attempts` counter already exists at `:839`).
**Exit criterion:** two distinct agent identities, with distinct tenant keys, concurrently claim → heartbeat → complete real jobs, event-notified, all attributable in the ledger and timeline.

### Campaign IV — GRAVEYARD TRIAGE (rolling, ~30 min/week) · *"Fix or bury with a headstone — never rot"*
Code-as-furniture applied to the census: ai-exec-pipeline → `_retired/`; inPACT redirect-stub trio (today.html/method.html/followup.html + dead today.js) decided; canvas-demo / c110-trace / webos-333 dispositioned; `lava-layers.json` metadata reconciled (openclaw marked non-load-bearing there but actively re-wired 07-06 — stale flag); ws-gateway gets a fate in Campaign III. Every kept item works; every buried item gets a dated deferral or a `_retired/` grave. The census table (in the festival) is the worklist.
**Exit criterion:** re-run census → zero contradictions between metadata, autostart, and reality.

### Campaign V — COMPOUND (continuous, after III) · *"The flywheel"*
The asymmetric-growth engine, assembled from everything above:

```
IDEA_REGISTRY (1,335 ranked, daemon-regenerated daily)
   → morning push proposes (Campaign I)
   → one tap promotes idea → task entity → work queue (/api/work/request)
   → agent fleet claims & executes (Campaign III)
   → receipts + deltas prove it (already READY)
   → closure rows feed the governor (Campaign 0)
   → mode ladder widens concurrency as trust compounds
   → wrap push reports: ideas shipped, loops closed, agent-hours, human-minutes
```

One number to steer by: **human-minutes per shipped item.** Falling = the prosthetic is working; the leverage is real and measurable.
**Exit criterion (the finish line of this plan):** one idea flows registry → push → tap → queue → agent → receipt → closure with **zero human keyboard time beyond the tap**, and that happens weekly without prompting.

---

## Part IV — What NOT to do (the guardrails, learned the hard way)

- **No new services or UI surfaces** until Campaign III's exit. The census found the graveyard grows every time building outruns wiring.
- **No runtime capability registration, ever** — including for "trusted" agents. Fleet onboarding = new tenants/tokens, never new ActionTypes/UASC verbs (Law 1; `research/uasc-m2m` reference impl stays quarantined).
- **No manager-only write paths** for execution data — inPACT and Atlas stay two views over one backend.
- **No starting Campaigns I-V while `build_allowed: false`** — that builds capability 21 for a system whose governor is begging for closure.
- **Don't retire the mode ladder** in the machine pivot — re-purpose it (Law 8). A substrate with no throttle is how an agent fleet burns money and trust.
- **No push inflation.** The ritual dies if the phone buzzes ten times a day. Morning, decisions-as-they-arise (capped), evening. That's it.

## Part V — Sequencing at a glance

| When | Campaign | Human cost | Agents' cost |
|---|---|---|---|
| Day 1 | 0 UNLOCK | ~30 min of one-tap decisions in loop_clearer | 2-3 h (two fixes + archive) |
| Week 1 | I RITUAL + II LIGHTS ON (parallel) | taps only | ~1 day + on-switches |
| Weeks 2-3 | III SUBSTRATE | review AGENT_SUBSTRATE.md, approve tenant keys | ~2-3 days |
| Rolling | IV TRIAGE | one weekly verdict session | 30 min/week |
| Continuous | V COMPOUND | the three touchpoints, permanently | the rest |

*Every task, with file:line evidence and provable Definitions of Done, lives in the fest festival `atlas-pivot`. Verify with `/groundwork verify` before completing anything.*
