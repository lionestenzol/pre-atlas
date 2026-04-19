# OPTOGON STACK — BUILD PLAN
*Maps the doctrine (01), contracts (02), and spec (03) onto concrete work in this repo.*
*Generated 2026-04-18.*

---

## 1. Layer Reality Check — What Exists Today

| Stack Layer (doctrine name) | Closest Thing In Repo | Status | Gap |
|:---|:---|:---|:---|
| **Site Pull** (Eyes) | None in this repo | Shipped on NPM per doctrine, not integrated here | No adapter that emits `ContextPackage` |
| **Optogon** (Brain stem) | None | Doctrine complete, zero code | Entire service |
| **Atlas** (Mind) | `services/delta-kernel/` + `services/cognitive-sensor/` + `atlas.ts` CLI | Real, running, leverage scoring exists | Doesn't emit `Directive` in Rosetta Stone shape |
| **Ghost Executor** (Autonomy) | `services/cortex/` (:3009, planner/executor/reviewer) + `services/uasc-executor/` (:3008, command executor) | Two separate pieces that together cover this role | Neither consumes `Directive` nor produces `TaskPrompt` in Rosetta Stone shape |
| **InPACT** (Hands) | `apps/inpact/` (:3006, today.html) | Product surface locked, light theme, Phase 2 live | No Signal ingestion; doesn't yet render cross-layer state |

**Critical insight:** Ghost Executor is not one thing in this repo. It is split across Cortex (agent orchestration) and UASC (command execution). The Rosetta Stone's Contract 3 → 4 flow maps onto **Atlas → Cortex → (UASC | Claude Code)**. Treat Cortex as Ghost Executor going forward; UASC stays as the tool-level executor beneath it.

---

## 2. Decisions Required Before Build (resolve these first)

| # | Decision | Options | Recommendation |
|:---|:---|:---|:---|
| D1 | Optogon language | Python (matches spec pseudocode, matches Cortex/UASC) / TypeScript (matches delta-kernel) | **Python** — spec is Python, and Optogon talks to Atlas via HTTP not in-process |
| D2 | Optogon port | :3010 next available | **:3010** |
| D3 | First real path to implement | `book_flight` (toy), `ship_inpact_lesson` (real), `close_cognitive_sensor_run` (real) | **`ship_inpact_lesson`** — tests doctrine against real work you already do |
| D4 | Where do Path JSON files live | `services/optogon/paths/` / `contracts/paths/` | **`services/optogon/paths/`** — paths are code, not contracts |
| D5 | Contract schemas location | `contracts/schemas/` (existing) | **`contracts/schemas/`** — consistent with ModeContract.v1.json, AegisPolicy.v1.json, etc. |
| D6 | Does Cortex get renamed to `ghost_executor`? | Yes / No / Alias | **No, alias** — keep service name, document that Cortex *is* the Ghost Executor role |

---

## 3. Build Sequence — Four Phases

Mapped to doctrine's Part 8 ("What To Build First"):

### Phase 1 — Contracts First (1–2 hours)
*Ground truth before any logic. JSON Schemas that every layer validates against.*

**Deliverables:**
- `contracts/schemas/OptogonNode.v1.json` — Section 6 of spec
- `contracts/schemas/OptogonPath.v1.json` — Section 7 of spec
- `contracts/schemas/OptogonSessionState.v1.json` — Section 8 of spec
- `contracts/schemas/ContextPackage.v1.json` — Rosetta Contract 1
- `contracts/schemas/CloseSignal.v1.json` — Rosetta Contract 2
- `contracts/schemas/Directive.v1.json` — Rosetta Contract 3
- `contracts/schemas/TaskPrompt.v1.json` — Rosetta Contract 4
- `contracts/schemas/BuildOutput.v1.json` — Rosetta Contract 4 response
- `contracts/schemas/Signal.v1.json` — Rosetta Contract 5
- `contracts/schemas/UserPreferenceStore.v1.json` — Rosetta cross-session memory
- `contracts/examples/` — one valid example per schema

**Success:** All 10 schemas validate their own example with `jsonschema`. Nothing else runs yet.

---

### Phase 2 — Optogon MVP Service (2–3 hours)
*The four things doctrine says must exist.*

**Scaffold `services/optogon/`:**
```
services/optogon/
  pyproject.toml
  start.bat
  src/optogon/
    __init__.py
    main.py                  # FastAPI server on :3010
    config.py
    node_processor.py        # Section 14 of spec
    contract_validator.py    # Contract Layer enforcement
    response_composer.py     # Pacing Layer — LLM call with constraints
    session_store.py         # In-memory + SQLite persistence
    context.py               # Context hierarchy (confirmed > user > inferred > system)
    inference.py             # Burden-Removal inference rules
    signals.py               # Emits Signal to InPACT
  paths/
    ship_inpact_lesson.json  # First real path
    _template.json           # Blank path for authoring
  tests/
    test_node_processor.py
    test_contract_validator.py
    test_pacing.py
    test_path_ship_inpact_lesson.py
```

**Endpoints (FastAPI):**
- `POST /session/start` — body: `{path_id, initial_context}` → creates session, returns `session_id` + first response
- `POST /session/{session_id}/turn` — body: `{message}` → processes user turn, returns response + current node state
- `GET /session/{session_id}` — returns full session state (debug/Inpact consumption)
- `GET /paths` — lists available paths
- `GET /health`

**Success metrics (from spec Section 11):**
| Metric | Target |
|:---|:---|
| Questions per Close | < 3 for 5-node path |
| Inference Accuracy | > 0.85 |
| Path Completion Rate | > 0.75 |
| Tokens per node closed | < 200 |

**Validation:** Run `ship_inpact_lesson` path end-to-end. Must close with deliverable = lesson content merged into `apps/inpact/content/lessons/`.

---

### Phase 3 — Wire Into Atlas + InPACT (1–2 hours)
*Make the existing layers speak the contracts.*

**3a. Atlas → Directive emitter**
- Add `services/delta-kernel/src/atlas/directive.ts` — transforms current task queue output into `Directive.v1.json` shape
- Add `GET /api/atlas/next-directive` to delta-kernel
- Validate output against schema on emit

**3b. Cortex as Ghost Executor**
- Add `services/cortex/src/cortex/ghost_executor/` module
- `consume_directive(directive: Directive) -> TaskPrompt` — reformats for Claude Code
- `emit_build_output(result) -> BuildOutput` — structured return
- Document in `cortex/README.md` that Cortex plays the Ghost Executor role

**3c. InPACT Signal consumption**
- Add `apps/inpact/signals.js` — fetches from `/api/signals`
- Add `GET /api/signals` endpoint in delta-kernel (aggregates from all layers)
- today.html renders `approval_required` and `urgent` signals above the fold per Section 11 display rules
- No new design surfaces — reuse existing today.html blocks

**Success:** Trigger an Optogon path end-to-end from InPACT → today.html shows the close signal + deliverable link.

---

### Phase 4 — Close Signal Loop + Preference Store (1 hour)
*Completes the feedback cycle.*

**Deliverables:**
- `POST /api/atlas/close-signal` in delta-kernel — accepts `CloseSignal`, updates task queue
- `contracts/schemas/UserPreferenceStore.v1.json` + backing store in delta-kernel (SQLite)
- Optogon populates `context_residue.learned_preferences` on close
- Atlas writes them to preference store
- Cortex reads preferences when composing next `TaskPrompt`

**Success:** Run `ship_inpact_lesson` twice. Second run asks fewer questions because the preference store learned from the first.

---

## 4. What We Are NOT Building (scope discipline)

Per doctrine Part 8 ("do not build everything Optogon could be"):

- Learning Layer (Layer 6 in spec) — deferred until after 10 real path runs
- Cross-layer Interrupt Protocol — documented in Rosetta Stone, not coded until two paths race
- Sub-routine forking — structurally supported in schema, not wired in MVP
- Full 8-agent Atlas architecture — stay on existing delta-kernel leverage scoring
- Site Pull integration — stays external until Phase 5+

---

## 5. First Real Path — `ship_inpact_lesson`

This tests the doctrine against work you already do.

| Node | Type | Qualification Keys | Actions |
|:---|:---|:---|:---|
| `entry` | qualify | `lesson_number`, `content_source` | — |
| `load_skeleton` | execute | — | Read `apps/inpact/content/lessons/{N}.md` skeleton |
| `validate_content` | gate | — | Check content_source exists and is non-empty |
| `merge` | execute | — | Merge content into skeleton using shared `ls-*` CSS (per `feedback_one_lesson_template.md`) |
| `preview` | execute | — | Start preview server, render lesson |
| `em_dash_check` | gate | — | Scan for em dashes (per `feedback_no_em_dashes_in_ui.md`) — FAIL if found |
| `approve` | approval | — | Bundle: "Lesson N ready. Preview at :3006/lessons/N. Commit?" |
| `commit` | execute | — | Git commit with conventional message |
| `done` | close | — | Emit `CloseSignal` with deliverable = commit SHA |

**Why this path:** it exercises qualify, execute, gate, approval, close node types. It uses real repo rules (em dash ban, shared CSS). It produces a real deliverable (a shipped lesson).

---

## 6. Risk Register

| Risk | Likelihood | Mitigation |
|:---|:---|:---|
| LLM pacing layer drifts despite constraints | High | Start with strict token budgets; measure `Questions per Close` on every run |
| Contract schemas go stale as code evolves | Medium | CI check that loads every schema + validates every example on commit |
| Cortex/UASC confusion ("which one is Ghost Executor?") | Medium | Document in `services/cortex/README.md` explicitly; Cortex *is* the role |
| "Three-hour MVP" timeline slips (it will) | Certain | Accept it. Doctrine says "3 hours" — plan says four phases. Don't conflate. |
| Path JSON authoring is painful | High | Phase 2 includes `_template.json` + `test_path_ship_inpact_lesson.py` as the authoring example |
| Active lanes (Code Converter, inPACT curriculum) starve | High | Optogon is a new lane, not a replacement. Explicit choice: pause one, or parallelize. |

---

## 7. Lane Choice — Where Does Optogon Fit

Current active lanes per MEMORY.md:
- Code to Numeric Logic MVP (ACTIVE)
- Mosaic Phase 4 (PAUSED)
- inPACT curriculum embodiment (ACTIVE BUILD)
- inPACT product pivot (ACTIVE)

Adding Optogon makes 3 active lanes. Options:

- **Option A:** Defer Optogon until one active lane ships. Keeps focus. Cost: doctrine cools.
- **Option B:** Phase 1 only (contracts) now. Then decide. Low cost, preserves optionality.
- **Option C:** Full build starting now. Cost: slows inPACT curriculum + code converter.

Recommendation: **Option B** — do Phase 1 (contracts) this session. It's 1-2 hours and produces 10 schemas that don't cost anything if you defer the rest. Decide on Phase 2 after seeing the schemas land.

---

## 8. Ready-to-Run Next Step

When you say go, Phase 1 begins:

1. Generate all 10 JSON schemas under `contracts/schemas/` with proper `$schema` and `schema_version` fields
2. Generate one valid example per schema under `contracts/examples/`
3. Add a `validate.js` or `validate.py` script that loads every schema + example and asserts validity
4. Update `contracts/README.md` to document the Optogon + Rosetta Stone schemas
5. Commit as `feat(contracts): optogon stack schemas v1`

No service code. No wiring. Just the contracts.

---

*This plan is downstream of the doctrine. If the doctrine says something different, the doctrine wins.*
