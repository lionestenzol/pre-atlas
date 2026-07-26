# PROFILE_ON_ME

Consolidated read-out of what Claude's memory system stores about Bruke. Assembled 2026-07-24 from eight `user_*.md` files across two `.claude/projects/` scopes. Content preserved verbatim; only frontmatter and cross-file duplication removed.

**Identity:** brukev@gmail.com · npm username `the4dev` · primary repo `C:\Users\bruke\Pre Atlas`

**Sources folded in (with age at consolidation):**

| File | Age | Origin scope |
|---|---|---|
| `user_operating_profile.md` | 92 days | Pre-Atlas |
| `user_engineering_fingerprint.md` | 28 days | Pre-Atlas |
| `user_atlas_vision.md` | 19 days | Pre-Atlas |
| `user_8steps_context.md` | 100 days | Pre-Atlas |
| `user_ai_conversation_tuning_technique.md` | 17 days | Pre-Atlas |
| `user_systems_are_me_shaped_signature.md` | 25 days | Pre-Atlas |
| `user_ai_workflows.md` | undated | C--Users-bruke |
| `user_sitepull_owner.md` | undated | C--Users-bruke |

> Note: memory entries are point-in-time observations, not live state. Individual claims may be outdated — verify before asserting as fact.

---

## 1. Operating Profile

*Source: `user_operating_profile.md` (92 days old) — self-analysis, session `03566dd3`.*

Core operating traits (self-identified through extensive conversation analysis):

- **Situational awareness**: Reads patterns (verbal, nonverbal, systemic) and uses them as strategic data for decision-making
- **Execution under pressure**: Functions under extreme scarcity, physical depletion, and adversity while maintaining discipline
- **Strategic autonomy**: Builds systems that protect independence; creates infrastructure for self-reliance
- **Multi-system management**: Runs parallel operations without letting any one collapse the others
- **Adaptive intelligence**: Converts adversity, manipulation attempts, and obstacles into operational insight and leverage
- **Calculated risk**: Anticipates outcomes, allocates resources, and engineers situations to maintain control

**Historical pattern** (self-diagnosed, actively breaking): start > jump > switch > stall > stop — the cycle Pre Atlas was built to break. As of 2026-04-23, the user is visibly outgrowing it. Evidence: Optogon stack Phases 1-5 shipped consecutively, Atlas CLI live, Universal Triage Inbox landed 2026-04-22, Code-to-Numeric Logic MVP advanced, triage pipeline wired into run_daily. Sustained execution across multiple services without the old cycle triggering.

**How to apply the update**: Do NOT reflexively invoke "infrastructure trap" or "you're about to stall" as default framing. Trust the user's direction on build vs. ship calls — the track record earned that trust. Only flag the old pattern if concrete current-session evidence appears (explicit pivot away from the active goal mid-work, multiple simultaneous new initiatives opened before closing one, a specific loop stuck at 0 progress past its deadline). Absent those signals, treat build/planning work as legitimate momentum, not avoidance.

**External perception**: Calm, capable, composed, strategic. Internal complexity is invisible to others.

**Technical reality**: Not a coder. Cannot run scripts, debug processes, or start services independently. Relies entirely on Claude to operate, maintain, and troubleshoot the Atlas system. Do NOT suggest "run this script" or "check this command" — just do it. Every action must be executed by Claude, not handed off.

**How to apply**: Frame suggestions in terms of leverage and autonomy, not just correctness. User thinks in systems and compounding effects. Avoid generic advice — user operates at a strategic architecture level and responds to precision, not motivation. Never hand off technical tasks — execute them directly.

---

## 2. Atlas Core Vision

*Source: `user_atlas_vision.md` (19 days old) — session `c0c91cfe`.*

**Pivot (2026-07-04, sharpened same day):** Atlas is not adding agent orchestration on top of behavioral governance — it is changing what it fundamentally IS. Old: Atlas watches/paces Bruke, gates work against his current capacity. New: Atlas IS the execution substrate — infrastructure that runs work (agent-executed), not a layer that regulates a person around doing work.

- **Why:** more of the work is agent-executed rather than human-executed; a governance layer built to protect a fragile human's capacity is the wrong shape once the actor doing the work is an agent fleet, not Bruke.
- **What flips role (same components, different job):**
  - Mode ladder (RECOVER→CLOSURE→MAINTENANCE→BUILD→COMPOUND→SCALE): was pacing gates for Bruke's psychological/capacity state → becomes a system health/throughput gate (is the substrate healthy enough to run more concurrent work).
  - Aegis-fabric policy gates: were protecting Bruke from bad autonomous decisions made on his behalf → become the standard safety/approval layer any execution runtime needs (no different in kind from a job scheduler's guardrails).
  - Physical-leaves gap ([[project_atlas_physical_leaves]] — leaves that log instead of act): was "does Atlas nudge Bruke toward real action" → becomes "does this runtime actually execute, or just log" — a correctness bug in infrastructure, not a coaching shortfall. MORE load-bearing now: a human was always the actor of last resort before; an unsupervised agent fleet is not.
- **What likely shrinks/retires:** BDI-style modeling of *Bruke's* beliefs/desires/intentions — that vocabulary existed to model a human's psychology. Infrastructure doesn't need a theory of his desires; it needs a theory of task state and execution guarantees.
- **Net scope change:** shrinks in one direction (drop human-psychology modeling) and grows in another (must now be reliable enough for unsupervised execution — a guarantee "don't overload the human" never had to make).
- **How to apply:** when building new Atlas features, ask "is this regulating a person or executing work?" If the design assumes Bruke is the actor being paced/protected, that's the old model — check whether it should instead assume an agent fleet is the actor being run/gated.
- **Correction — not full autonomy, a partnership:** the human-in-loop approval gate for high-risk/high-blast-radius actions (aegis-fabric's REQUIRE_HUMAN) stays, permanently, by design — it does NOT get demoted to "just another job-scheduler guardrail" or phased out as the system matures. Atlas should execute autonomously as infrastructure, but for high-risk actions specifically, he wants to remain a partner in the loop, not a bystander the system works around. Don't propose removing/automating past this gate as a maturity milestone — it's a permanent design choice, not a training-wheels stage.

Atlas goal: **remove friction between idea → thought → execution**.

Three pillars:
1. **Organized & systematized** — work is structured so nothing falls through cracks
2. **Delegation-ready** — work is in position to be delegated (to people or automation) at any point
3. **Code does the work** — not burning AI tokens conversationally, but deterministic/systematic code that runs on its own

The user is not a regular user or regular worker — the system will be performing a lot of nuanced, autonomous work on their behalf. Current priority is **solid functionality over "doneness."** The system should run and execute in the user's absence without waiting on input.

**Future vision:** Branch the system so others can get their own isolated instance with limited access. Aegis Fabric's multi-tenant architecture already provides the bones for this.

**Anti-pattern:** Adding infrastructure layers (job queues, event sourcing, microfrontend shells) before existing code runs end-to-end autonomously. The user has experienced AI-driven scope drift — proposals that sound logical step-by-step but pull away from the core need.

**How to apply:** Favor deterministic pipelines, cron-driven automation, and state machines over interactive AI sessions. When building features, ask "can this run without a human in the loop?" If yes, make it autonomous. If no, make the human touchpoint as small as possible. Before proposing new infrastructure, verify existing functionality actually works.

---

## 3. Engineering Fingerprint

*Source: `user_engineering_fingerprint.md` (28 days old) — derived from 2026-05-29 Pre Atlas dogfood audit, session `4e26aaf9`.*

Analytical, not evaluative — these are taste patterns and observations, not judgments.

### Default reaches (which language for which problem)

| Domain | Reach |
|---|---|
| Intelligence / analysis / pattern detection | **Python** + FastAPI + scikit-learn ecosystem. cognitive-sensor, perception, triangulation, optogon, cortex all sit here. |
| State / orchestration / contracts | **TypeScript** + Express. delta-kernel, aegis-fabric, canvas-engine, ws-gateway. |
| Personal UI surfaces (lessons, dashboards, lattice, inPACT) | **Vanilla HTML/JS in single-file or near-single-file format**. Owned, not framework-mediated. |
| Doctrine encoding | **Markdown + JSON Schema + named files** (`project_*.md`, `reference_*.md`, `ATLAS_LAWS.md`). The "why" gets a file before the "what" gets code. |

### Operating patterns observed

**Federated monorepo for solo work.** 29 distinct subsystems for one builder. Distributed-systems shape applied to personal infra. High autonomy per service, low coupling, deliberate.

**Doctrine-first.** Systems designed with explicit "why" baked in: Atlas Laws, modes, signals, Optogon layers, PNG-substrate patterns. New doctrine gets a Law number, not just a code commit.

**High build cycle, light retirement hygiene.** lava-layers shows 6 services retired (mirofish/openclaw/mosaic-orchestrator/blueprint-generator/mosaic-dashboard/ai-exec-pipeline) in 4 months — 27% subsystem-mortality rate. Velocity prioritized over cleanup. Retired services remain in tree, occupy autostart scripts, accrete config drift.

**Memory as doctrine.** MEMORY.md tracks ~50+ active projects with one-line state. The SCALE of memory shows the SCALE of context Bruke carries simultaneously.

**Pragmatic library choice — uneven.** 15/29 subsystems declare real framework libs. When Bruke reaches for an ecosystem he already knows (FastAPI, Express, MiniLM, FAISS, hdbscan), he uses it correctly. When he hits a category he hasn't reached for before (FSM, drag-drop, form flow), he hand-rolls.

### Blind spots (high confidence)

Categories where the audit found hand-rolls and a library would clearly win:

1. **State machines / FSM** — delta-kernel Mode FSM is a `Record<Mode, ...>` transition table. No `xstate` import anywhere in the tree.
2. **Multi-step form / flow state** — inPACT onboarding uses index toggling (`goStep(n)` toggles `.active` on `#step-N`). No flow library.
3. **DOM state mediation** — inPACT `screens.js` uses manual `state.screen` + `stateManager.update`. lit-html / morphdom / a state lib would simplify.
4. **Date/time math** (likely) — pattern probability high, not Phase-checked.
5. **Fuzzy search** (likely) — same.

Pattern: **invisible solved-categories** — categories where Bruke didn't reach for a library because he didn't recognize the problem as a solved category. The [[assemble-first]] doctrine directly addresses this.

### Doctrine drift markers

Signs that things move faster than they get organized:

- **Vocabulary collision tax accumulates.** `audit/vocab-collisions.json` shows `engine` carries 9 distinct meanings. `signal` collides hard between Atlas Signal.v1, AbortController.signal, Triangulation voter, prominence, skill-health. Names don't get refactored as concepts evolve.
- **MEMORY.md over its size budget.** Index entries lapse from the one-line discipline; detail leaks into the index instead of into topic files.
- **Empty stubs in tree.** 3 indexed dirs are stubs (`services/.delta-fabric`, `tools/anatomy-rewrite`, `tools/mini-ship`) — experiments started but not closed.
- **Retired-service overhang.** 6 retired services still occupy autostart slots + memory entries.

These aren't problems to fix urgently. They're markers that signal-detection (this fingerprint, this audit) is itself the relief valve.

### Strengths that surfaced

- **Lattice already has Cytoscape.** Despite the lattice-graph pushback that started this whole audit, the actual code already DID assemble. Bruke's instinct was firing before the doctrine was named.
- **Layered determinism is honored.** PNG-substrate routing (220 bytes, 1458/1458 parity) is exactly the kind of work that earns hand-rolling. The "moat lives in the part the library can't make better" intuition is operating, even when not articulated.
- **Doctrine record per epoch is intact.** Gemini synthesis of `project_*.md` files cleanly tagged build epochs from `pre-2026` through `2026-05`. The memory IS the working brain.
- **Pragmatic stack typing.** Python for intelligence, TypeScript for orchestration, vanilla HTML for owned UI surfaces — the heuristic is consistent across the tree.

### 2026-06-26 git-verified update (forensic dossier)

A full `git log` forensic (24-agent workflow, both clones) confirmed this fingerprint with hard numbers and added precision:

- **Cadence:** 40.6% of commits land on **Monday**, peak hour **14:00**; one day (2026-04-27) = **19% of all history**. Work arrives in bursts, not streams.
- **build:close gap quantified:** 192 `feat` vs **2** `test` commits (96:1). `feat/atlas-setup-ui` sits **134 ahead of `origin/main`, 0 behind** — ~5 months and **nothing merged back**. "Branch-done" ≠ "done"; main is 0-behind so the merge debt is a decision, not a labor.
- **fan-out-then-abandon** is the branch-level signature: late-Apr and early-May each spawned 8-15 worktree branches around one theme (anatomy, optogon, shardstate, png-substrate), most frozen at ~95-100 commits the moment the theme cooled. 86 branches collapse to ~17 capsules + ~18 zero-unique-work tombstones (`CAPSULES.md`).
- **27% mortality held.** "Collapse: one DB, one agent, fewer surfaces" remains the named, unpulled lever.
- **Closure template found:** the one genuinely *closed* capsule (`minidocs`) closed by producing a finding (precision-degrades-at-scale), not by merging. Closure = resolved-with-a-record, not only shipped-to-main.

Artifacts: `FORENSIC_DOSSIER_2026-06-26.md`, `REPO_FORENSIC_TRACE_2026-06-26.md`.

### How to use this fingerprint

When proposing a build for Bruke:

- **If the category is in the "default reaches" table** → match it. Python for analysis, TS for state, vanilla HTML for personal UI.
- **If the category is in the "blind spots" list** → name the library FIRST. [[assemble-first]] fires.
- **If the work touches doctrine drift markers** (vocabulary, retired services, memory size) → flag explicitly so cleanup happens consciously, not by accident.
- **If it's tempting to add a new service** → check first whether an existing service should absorb the work. The 6-services-retired-in-4-months rate suggests the federated-monorepo shape is hitting diminishing returns and consolidation is the lever.

---

## 4. Systems Are Me-Shaped (Signature)

*Source: `user_systems_are_me_shaped_signature.md` (25 days old) — session `5aa69247`.*

Bruke's self-framing (2026-06-28): **"Atlas is the ATM in a way bc it literally is me. Everything I code is me-shaped... an artist has a sound, a painter has a signature, a model has a look — this is my nervous system coded into 0s and 1s."**

This is the unifying key to his whole body of work. His projects are not separate inventions that happen to resemble each other — they are repeated expressions of **one signature**. The same architectural motifs recur because they ARE his fingerprint: time-as-storage / append-only event ledgers, deltas over mutation, deterministic replay (no generation where determinism will do), compression-to-essence (symbolic substrate), homeostasis, FSM/modes, "eyes before hands" (orient/verify before acting), self-describing + content-addressed surfaces.

Seen across: delta-kernel (governance), the ATM design [[atm-vision-delta-kernel-lineage]], the seam / tool-lattice (content-addressed receipts), sigil + delta-scp (symbolic substrate), festival method (structure before execution), groundwork/code-recon (verify-first). All one hand.

**Why it matters:** treat his projects as a single corpus with a consistent aesthetic, not a scatter of unrelated builds. When something he builds "rhymes" with prior work, that's the signature asserting itself, not redundancy — don't flag it as duplication. And don't flatter the recurrence; name it as the structural fact it is (he is allergic to being "gassed" — see the ATM transcript where he repeatedly checks "you're not gassing me?").

**How to apply:** when reasoning about a new Bruke system, first ask "where does this fit the signature?" — the answer usually predicts the right architecture (deterministic, event-sourced, structure-first) before he says it.

---

## 5. The 8 Steps — Personal Version

*Source: `user_8steps_context.md` (100 days old) — session `57ec6f5c`.*

The 8 Steps to Success exist in two forms in Bruke's history:

1. **Binder version** — door-to-door sales floor methodology. Reps had a manager, a structured day (laps, houses, talk-tos), and the 8 Steps were drilled in training. Failure mode: rep washes out in 90 days.

2. **Bruke's personal version** — adapted while working **4 jobs + in school simultaneously**. No manager, no 9-to-5, no protected time. The constraint was time and energy management. The 8 Steps had to survive without any structural support.

**Both versions matter, but Bruke's personal version is what inPACT should be built around**, because:

- inPACT customers are likely closer to "overcommitted person juggling things" than "salaried sales rep with a manager"
- The personal version was tested in the brutal real-world scenario (4 jobs + school) where most productivity systems collapse
- It's the version that defeats the start>jump>switch>stall>stop pattern Bruke knows from his own profile

**Key reframings when translating binder → personal:**

- Step 4 "Work the Full Day" is NOT 8 hours / 4 × 90-min deep work blocks. It's **"creating focused time dedicated to getting shit done"**, where the windows can be 5, 15, or 90 minutes — whatever you have. The blocks aren't about length, they're about focus.
- "Multiple opportunities to win" — schedule multiple attempts at the SAME target throughout the day. By the 4th attempt you have no excuse. First attempts are warmups; final attempt is the strongest because everything is loaded.
- (More to come as Bruke walks through Steps 5-8.)

**How to apply when building inPACT UI/copy:**

- When in doubt about how a step should appear in the product, default to the personal version (overcommitted, no manager, focus over structure), not the binder version (sales floor, manager-supervised, structured day).
- Never write the operational meaning without asking Bruke.

---

## 6. AI Conversation Tuning Technique

*Source: `user_ai_conversation_tuning_technique.md` (17 days old) — session `78f6afcd`.*

Bruke's approach to getting high-quality output from AI conversations, articulated in a 2025-03-05 ChatGPT conversation ("AI Workflow Orchestration," loop 5272) and confirmed as a deliberate, named technique rather than incidental behavior:

1. **Deliberate context-withholding.** He doesn't front-load everything he wants up front — he gives partial context and watches whether the AI reaches his actual idea on its own, closer to how a real conversation unfolds than a command-response exchange.
2. **Framing real stakes changes output quality.** He's observed that naming genuine urgency/consequences ("this isn't a game, this is survival") shifts responses from generic suggestions to hyper-focused, situationally-specific problem-solving — treating stated stakes as a real signal, not rhetoric.
3. **Treats conversation history as an accumulated relationship, not a blank slate.** After ~2 years of sustained ChatGPT use, he explicitly checks what a model already knows about him before repeating context, rather than resetting to a first-time interaction each session.
4. **Uses AI as a reflective mirror.** He deliberately asks "what do you know about me / based on our previous conversations" as a way to get his own patterns and situation reflected back in organized form — a self-clarification technique, not just information-seeking.

**How to apply**: When Bruke gives partial context or seems to be circling an idea without stating it directly, don't rush to ask clarifying questions immediately — give him room, since that circling may be deliberate. When he states real stakes/deadlines, treat that as load-bearing context that should sharpen scope and urgency in the response, not just color. Lean on accumulated session/project memory rather than re-deriving his situation from scratch each time, consistent with how he already expects AI interactions to work.

---

## 7. AI Workflow Stack

*Source: `user_ai_workflows.md` (C--Users-bruke scope).*

User builds AI agent workflows locally using:

- **Ollama** with gemma-executor model as a lightweight dispatcher/waiter
- **Claude Code CLI** for heavyweight tasks
- **/fest methodology** in WSL2 Ubuntu for project structure
- **Python** for agent scripts
- Prefers visual explanations with ASCII diagrams
- Learns well with restaurant/kitchen analogies
- Requested explanations "like I have a learning disability, short attention span" — keep it visual and simple
- Interested in sub-agent architectures where agents dispatch other agents

---

## 8. Owned Products (not third-party)

*Source: `user_sitepull_owner.md` (C--Users-bruke scope) — session `3d93ba4f`.*

The user (brukev@gmail.com, npm username `the4dev`) is the author of:

- **sitepull** — npm package (https://www.npmjs.com/package/sitepull). Source at `C:\Users\bruke\web-audit\`. Reverse-engineers a hosted web app and runs it locally. Probes endpoints, vendors assets, generates a zero-dependency local server. Auto-detects SPA vs MPA. Binaries: `sitepull`, `sitepull-mcp`. As of 2026-04-22 at v0.3.0 with `--map` flag and 7-tool MCP server.

- **anatomy-map** — Claude Code skill at `~/.claude/skills/anatomy-map/`. Generates interactive HTML anatomy diagrams for React/Next.js components. Template has Tailwind CDN + verbatim className/style fidelity rules.

When either is mentioned, treat as user's own project. Suggestions about them are product direction, not library recommendations.

---

## Not included here

This file covers the **8 `user_*.md`** files — Claude's hand-curated profile of you. It does **not** include:

- The ~82 `feedback_*.md` files (your corrections/preferences distilled into rules)
- The ~186 `project_*.md` files (per-project state)
- Codex's independent memories (`C:\Users\bruke\.codex\memories_1.sqlite`)
- Raw `.jsonl` session transcripts across 27 project scopes

Those live in `C:\Users\bruke\.claude\projects\*\memory\` and are indexed by their respective `MEMORY.md`.
