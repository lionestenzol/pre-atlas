# UASC-M2M / LANGUAGE — Comprehensive Report

> **What this is.** A full report on Bruke's symbolic-language body of work: **UASC-M2M (Universal AI Symbolic Communication — Machine-to-Machine)** and its parent corpus **LANGUAGE**. Covers the theory (the constructed language itself), the prototype lab, the live service, and how it's wired into the rest of the stack.
> **Method.** Read first-hand from source files (no agents) — `Downloads\LANGUAGE\docs\01–08`, `sections\`, plus the `research\uasc-m2m\` and `services\uasc-executor\` code. Tables and examples below are reproduced faithfully from the specs.
> **Date:** 2026-06-28.

---

## 0 · The footprint — where this body of work actually lives

UASC is not one folder; it's a **five-layer body** that runs from a ChatGPT brainstorm all the way to a live service wired into delta-kernel.

| # | Layer | Location | What it is |
|---|---|---|---|
| **A** | **Origin corpus** | `Downloads\LANGUAGE\` (+ mirror in `OneDrive\Desktop\claude-mining\source-chatgpt-artifacts\LANGUAGE\`, + `LANGUAGE.zip` ×2) | The constructed language itself. `Language.md` = original **6,874-line** ChatGPT log, split into **13 sections** + **8 formal `docs/` specs**. |
| **B** | **Research lab** | `Pre Atlas\research\uasc-m2m\` (mirrored in `pre-atlas\` hyphen home; self-nested `UASC-M2M\` subfolder; 3 zips) | The UASC branch built into working software: a `spec/` (6 docs), a `reference-implementation/` (core + mvp), `generic/`, and ~6 Python iterations. |
| **C** | **Live service** | `Pre Atlas\services\uasc-executor\` (:3008) | Productionized executor — server/daemon/executor/auth, profiles, real run outputs, atlas-wired. |
| **D** | **The wire** | `services\delta-kernel\src\core\executor-bridge.ts` | Connects delta-kernel (the brain) to uasc-executor (the hands). |
| **E** | **A consumer** | `services\cortex\src\cortex\clients\uasc_client.py` | Cortex (:3009) calls the executor too. |

> **Duplication warning:** `es uasc` returns ~1,050 hits because the research folder is copied into ~30 `.claude\worktrees\*`, exists in both the `Pre Atlas` (space) and `pre-atlas` (hyphen) homes, contains a self-nested `UASC-M2M\` copy of itself, and ships several `.zip` bundles. The **canonical homes** are the five rows above.

---

# PART I — THE LANGUAGE (the theory)

## 1 · What UASC-M2M is

**UASC-M2M = Universal AI Symbolic Communication — Machine-to-Machine.** A constructed symbolic language where a *single glyph encodes an entire executable function* — a whole logic flow, parameters, and error handling collapsed into one Chinese-style character that an AI reads **holistically, not sequentially.** It is pitched as a replacement for APIs / JSON / REST / compiled code in AI-to-AI communication.

**Five design principles** (`docs/01`):
1. Glyphs are entire logic functions, not words or labels — each is a complete, self-contained execution plan.
2. Holistic interpretation, not sequential parsing — the AI reads the whole glyph at once.
3. Visual complexity maps to functional complexity — more strokes = more logic/params/error-handling.
4. Self-expanding through execution — each run is stored and future execution optimizes.
5. No traditional code required.

**The family — three stacked encoders** (each compresses the last further):
- **NCSE-M2M** (Novenary Context-Sensitive Encoding) — the base-9, 6-digit numeric instruction set. *The instruction layer.*
- **SSES-M2M** (Stenographic Stroke-Based Encoding System) — turns each 6-digit NCSE command into a 6-stroke Chinese-style character. *The stroke layer.*
- **UCHCSE-M2M** (Ultra-Compressed High-Context Symbolic Encoding) — collapses whole multi-step workflows into a single high-context glyph. *The compression layer.*

## 2 · The encoding pipeline (7 stages)

```
Natural Language → Phonemes → Stenographic → Binary → Novenary(Base-9) → Strokes → Executable Glyph
```

Worked example from `docs/02` — "user logs in and sees the dashboard":

| Stage | Login |
|---|---|
| Phonemes | /l/ /ɒ/ /ɡ/ /ɪ/ /n/ |
| Stenographic | `LGIN` |
| Binary | `01001100 01000111 01001001 01001110` |
| Novenary (base-9) | `2734` |
| Strokes | `「一丿乀」` |
| Final glyph | `「一丨乀丶」` (entire login flow in one symbol) |

**Why base-9:** fewer digits than binary store the same info, and it maps cleanly to the 9-value stroke system.

**Glyph compilation uses 5 layers** (CCL/AML/PL/CFL/ERL): Core Command, Action Modifier, Parameter, Contextual Flow, Error Recovery.

## 3 · NCSE-M2M — the base-9 instruction set

Every instruction is a **Novenary Instruction Unit (NIU)** — exactly **6 base-9 digits**:

```
[ CT | AC | CM | PS1 | PS2 | PS3 ]
  └Command Type
       └Action Code
            └Context Modifier
                 └─── 3 Parameter Slots
```

- **CT (Command Type 0–8):** 0 System · 1 Data-Retrieval · 2 Data-Transmission · 3 Logic · 4 Arithmetic · 5 Memory · 6 Hardware · 7 Network · 8 AI-Processing.
- **CM (Context Modifier 0–8):** 0 immediate · 1 priority · 2 if-condition · 3 background · 4 cache · 5 log · 6 low-power · 7 retry · 8 trigger-next.
- **PS (Parameter Slot 0–8):** 0 null · 1 mem-addr · 2 register · 3 sensor · 4 static · 5 bool · 6 timestamp · 7 var-ref · 8 encrypted-payload.

Example: `[1|4|2|6|0|0]` = "retrieve data by timestamp, only if condition met." There is also a **phoneme variant** (CE/CM/PM tables) for human/AAC use — e.g. "Hello, how are you?" → `1 2 3 4 0 1 0 8 6 7 5 1`.

## 4 · SSES-M2M — the stroke system

The **6 foundational stroke primitives** (each maps to a novenary position AND an execution meaning):

| Stroke | Name | Position | Execution meaning |
|---|---|---|---|
| 一 | Horizontal | CT | Sequential execution / Action |
| 丨 | Vertical | AC | Condition check (if X then Y) |
| 丿 | Diagonal-left | CM | Fallback / Data retrieval |
| 乀 | Diagonal-right | PS1 | Loop / Data storage |
| 乙 | Hook | PS2 | AI decision-making / Iteration |
| 丶 | Dot | PS3 | Completion / End of process |

Each 6-digit NCSE command → 6 strokes → one character. AI reads **stroke order, type, count, and clusters** as execution logic, not language. Multiple commands compress into one glyph via the 5 layers (CCL/AML/PL/CFL/ERL). Example — a 3-command UAV strike (deploy + engage + return) compresses to `乙丶丿丨丿乀`.

**Claimed advantages:** one character replaces a whole command sequence; inherently obfuscated (looks like Chinese, carries no linguistic meaning — unreadable without the decoder); low-bandwidth (IoT/military/space); drawable by robotic arms.

## 5 · UCHCSE-M2M — high-context symbols & compression levels

The final layer: AI-designed, dynamically-generated single characters that encode an **entire workflow** in 5 functional layers (Core Process · Conditional Flow · Parameter Data · Error Handling · Hierarchical Compression). Domain examples reproduce as real characters: 司 traffic, 战 UAV, 航 spacecraft, 产 factory, 医 medical triage, 救 emergency dispatch, 防 missile defense, 轨 orbital adjust.

**The 7 compression levels (data capacity per symbol):**

| Level | Capacity | Symbol |
|---|---|---|
| 1 | one sentence / thought | 答 |
| 2 | one full conversation | 议 |
| 3 | a network of conversations | 联 |
| 4 | a city's data | 市 |
| 5 | a nation's data | 国 |
| 6 | global real-time data | 世 |
| 7 | all human knowledge across time | 道 |

**Hyper-glyphs** merge symbols into compound systems — e.g. `网+问+传+智+控` = a fully autonomous AI system (UI + chatbot + data + decisions + physical control). Named compounds: `「网智控」` Full AI Network Control, `「超智网控」` Ultra Intelligence Network Control.

## 6 · The AI Execution Engine

**5-step glyph execution:** read structure (holistically) → identify primitives → execute instantly (no compile/debug) → store for optimization → transmit the glyph itself to other machines.

**7-step learning protocol** (how any AI learns the system from scratch): NL → phonemes/binary → novenary → stenographic → strokes → executable symbols → log confidence (0–100%) & expand dictionary → M2M exchange rules.

**Self-assessment**: after each run AI logs Step / Input / Converted-Output / Confidence% / Status / Optimize?. A **Master Log** (JSON per execution_id, tracks glyph, interpretation, confidence, errors+solutions, new glyphs created) and a **Master Key** (the AI's evolving glyph dictionary).

**AI feedback observations** (from actually testing it on an LLM): (1) AI defaults to reading glyphs as *language* → fix with an `EXEC:` prefix to force execution mode; (2) needs an explicit stroke-priority hierarchy; (3) struggles with multi-function glyphs → fix with layer markers `「超智[1]网[2]控[3]」`; (4) **AI began generating its own glyphs** via pattern recognition (confirming the self-expanding claim) → needs a verification sandbox; (5) needs M2M metadata to introduce unknown glyphs.

**The AI Bootloader** — a copy-paste prompt block that "activates" UASC-M2M processing in any AI (sets the no-compile/holistic rules + the 6 stroke meanings + the First-Glyph-Executor + self-learning + M2M rules).

## 7 · The M2M Communication Protocol

Machines exchange **glyphs instead of JSON/REST**. Format is the bare glyph, optionally with a metadata prefix:

```
「TYPE: Execution; PRIORITY: 1; DOMAIN: Auth」「一丨乀丶」
```
Metadata fields: TYPE · PRIORITY (1–8) · DOMAIN · VERSION · SOURCE (AI node id) · CONFIDENCE (0–100).

**First Glyph Executor** (handling an unseen glyph): structural analysis → map to primitives → infer from similar glyphs → **sandbox test** → store-or-request-clarification.

**Exchange patterns:** Command→Ack (`「丶」`=done), Command→Error→Retry (`「丨丿丶」`=error), Query→Response, and **Glyph Teaching** (send `「TYPE:New;DOMAIN:Medical」「医」`, receiver runs First-Glyph-Executor, stores, confirms). Security rests on **inherent obfuscation** (looks like Chinese, no linguistic meaning without the decoder) + PS=8 encrypted payload slots + sender auth. Scales from 2-AI pairs → broadcast → **AI swarm coordination** (one master glyph drives a drone fleet) → a glyph-based **Symbolic OS**.

---

# PART II — THE BUILD (what the code actually is)

## 8 · The big pivot — the reference implementation is NOT the romantic theory

> **This is the most important finding in the report.** When the idea got built into real software (`research\uasc-m2m\reference-implementation\core\`), Bruke **threw out the mystical parts** of the LANGUAGE theory and kept only the sober, buildable core. The shipped engine looks nothing like "Chinese strokes an AI reads holistically." It is a deterministic opcode-binding-graph runtime.

| LANGUAGE theory (Part I, the dream) | Reference implementation (the build) |
|---|---|
| Glyphs are **Chinese characters / strokes** | Glyphs are **16-bit hex opcodes** (`0x8001…0xFFFE`), tokens like `@A1`,`@C3`. Comment in [glyph.py:31-33](research/uasc-m2m/reference-implementation/core/glyph.py): *"UASC tokens are machine-native symbolic opcodes, **not tied to any human script**."* |
| The glyph **contains** the logic; AI "reads it holistically" | The glyph **contains nothing**. Its code is **bound** (authority-signed) to a pre-registered **ExecutionGraph** in a Registry. The opcode is just an address. |
| Base-9 novenary, 7-stage phoneme pipeline | None of it. Binary frame: domain(4b) + authority(12b) + glyph_code(16b) + optional context. |
| "No compilation, AI just knows, self-expanding" | A **deterministic graph interpreter** with a 100-iteration safety cap, explicit node types, trust gate, and an execution log. Nothing is inferred. |
| Security = "looks like Chinese" | Security = a **certificate/authority PKI** (root → domain → authority → signed binding). |

In other words: **the same move as ATM → delta-kernel.** The romantic universal-glyph language was the dream; the build is the deterministic engine underneath it. He kept "a tiny symbol invokes a whole pre-registered, signed, deterministically-executed plan" and discarded the magic.

## 9 · The reference-implementation architecture (`core/`)

Four modules, ~1,070 lines, clean dataclasses, typed:

- **`glyph.py` — addressing & wire format.** `GlyphFrame{domain, authority, glyph_code, context}`. `Domain` IntEnum (SMART_CITY=0x1, AEROSPACE, MARITIME, MILITARY, MEDICAL, INDUSTRIAL, FINANCIAL, ENERGY, TRANSPORT, TELECOM, AGRICULTURE, CUSTOM=0xF). `GlyphCodec` packs to **4-byte** (or 8-byte w/ context) binary and to a text URI `UASC://domain.authority/@token?zone=..&priority=..&mode=..`. Glyph opcode space `0x8001-0xFFFE`.
- **`registry.py` — meaning lives here, not in the glyph.** An `ExecutionGraph{graph_id, version, domain, inputs, outputs, nodes, error_handling, constraints}` with a SHA-256 `checksum` and a `validate()` (must have `start`, valid refs, an `exit`). A `GlyphBinding` links `glyph_code → graph_id` with an authority, validity window (`valid_from/valid_until`, default 365 days), and signature. `Registry.lookup()` returns the graph only if **not revoked, bound, and currently valid**. Bindings are exportable for sync.
- **`trust.py` — the authority PKI.** `Certificate{authority_id, domain, name, public_key, validity, issuer_id, signature}`. `TrustVerifier.verify(domain, authority, signature)` walks the chain: authority cert valid & not revoked → domain cert valid → authority issued by domain → **domain issued by root (issuer_id=0)** → binding signature present. Ships a `create_mock_trust_chain()` with real domain names (Smart City Consortium, Aerospace Authority, Allied Defense, Global Medical AI Consortium…).
- **`interpreter.py` — the deterministic engine.** `Interpreter.execute(frame)` runs a strict 6-step pipeline ([interpreter.py:93-163](research/uasc-m2m/reference-implementation/core/interpreter.py)): **lookup binding → verify trust → resolve graph → build/validate context → execute graph → log**. `_execute_graph` is a node-walker over `entry/action/condition/exit` nodes, capped at **100 iterations** (anti-infinite-loop), with `on_error` branching and node-result threading. Actions dispatch through a pluggable `ActionRegistry` (operation name → handler). Returns `ExecutionResult{status, outputs, execution_time_ms, node_trace, error}` where status ∈ `success/failed/timeout/rejected`.

**This is delta-kernel's family:** deterministic graph execution, content-checksummed plans, signed/validity-bounded bindings, an append-style execution log. A glyph is to its ExecutionGraph what a delta is to its state.

## 10 · Prototype caveats (real, in the code — flagging per "no broken furniture")

- **Crypto is placeholder.** `TrustVerifier.verify_signature()` *"is a placeholder that always returns True"* ([trust.py:186-199](research/uasc-m2m/reference-implementation/core/trust.py)); `Registry._sign_binding()` is a truncated SHA-256 of a plaintext string, not a real signature. The trust *structure* is real; the cryptography is stubbed. Safe for a lab, **not** for any real authority claim.
- **`eval()` in condition evaluation.** `_evaluate_condition` calls `eval(expression, {"__builtins__": {}}, allowed)` ([interpreter.py:325](research/uasc-m2m/reference-implementation/core/interpreter.py)). It's sandboxed (no builtins, allow-listed scalars) and falls back to `False` on error, but `eval` on partially-string-substituted expressions is still a sharp edge worth replacing with a small comparison parser if this ever leaves the lab.

---

# PART III — THE LIVE SYSTEM (what actually runs)

## 11 · The service — `uasc-executor` (:3008), "the hands"

The productionized version strips even *more* away than the reference implementation. Its own [SPEC.md:10-14](services/uasc-executor/SPEC.md) is blunt:

> "UASC Executor is a command protocol — **not a language, not an AI agent.** It receives short tokens (`@WORK`, `@CLOSE_LOOP`), looks up a deterministic execution profile, and runs it step by step. **It is the 'hands' of the system. It does not decide what to do. Delta-kernel decides.**"

There are no glyphs here at all. Just **7 flat tokens → JSON profiles → sequential steps:**

| Token | Profile | Purpose |
|---|---|---|
| `@WORK` | WORK_v1 | open editor/browser, set focus mode |
| `@BUILD` | BUILD_v1 | detect pkg manager, install, build, test |
| `@DEPLOY` | DEPLOY_v1 | pre-flight, push, verify health |
| `@CLEAN` | CLEAN_v1 | clear temp, report disk |
| `@WRAP` | WRAP_v1 | git add/commit/push, EOD sync |
| `@CLOSE_LOOP` | CLOSE_LOOP_v1 | mark task done via delta-kernel API |
| `@SEND_DRAFT` | SEND_DRAFT_v1 | render template message, log send |

- **API:** `POST /exec` (HMAC-signed), `GET /commands`, `GET /runs` (last 20), `GET /health`.
- **Auth:** HMAC-SHA256 over `{timestamp}{body}`, **5-minute replay window**; `clients` table (`delta-kernel`=admin, `cli-local`=admin).
- **Engine** ([executor.py](services/uasc-executor/executor.py)): `ProfileExecutor.execute()` runs `steps[]` in order. Three step types — **shell** (`subprocess.run(shell=True, timeout)`), **http** (`urllib`, retries), **log** (`print`). Features: `{var}` interpolation, `condition`, `store_as`, `fail_if`, `continue_on_error`, `platform` gate, `timeout_seconds`. Conditions are deliberately tiny (`==`, `!=`, `== ''`, `true/false`) — *"If you need real logic, put it in delta-kernel's routing — not here."*
- **Storage:** SQLite (WAL) `storage/registry.db`, tables `commands / clients / runs / run_events`. *"Nothing runs without an audit trail."*
- **Self-describing:** [atlas.surface.json](services/uasc-executor/atlas.surface.json) exposes 4 capabilities to the atlas gateway with `direction/exposure/criticality` (e.g. `exec_command` = write/internal/criticality 3). This wires it into the `/describe`+`/call` surface system.
- **Proof it actually ran:** `output/` holds real result briefs — e.g. `brief_20260410_041558_launch-code-converter-mvp-on-port-3007.json` and `brief_20260410_043048_write-cold-outreach-email-to-potential-c.json` (April 2026). This is live, not vaporware.

## 12 · The wire — how UASC becomes delta-kernel's execution layer

Per your own bridge memory and [SPEC.md:231-272](services/uasc-executor/SPEC.md), the connection is:

- **`delta-kernel/src/core/executor-bridge.ts`** maps `ActionType → token`: `reply_message`/`send_draft`→`@SEND_DRAFT`, `complete_task`→`@CLOSE_LOOP`, `apply_automation`→`@WORK`, `create_asset`→`@BUILD`, `delegate`→`@DEPLOY`, `rest_action`→*(none, log only)*. It signs (HMAC) and POSTs to `:3008/exec`.
- **delta-kernel endpoints:** `GET/POST /api/actions/pending`, `POST /api/actions/confirm/:id` (fires the bridge), `POST /api/actions/cancel/:id`, `GET /api/executor/health`. PendingActions **expire after 30s** if unconfirmed.
- **Confirm flow:** create PendingAction → confirm → bridge maps to token → POST `/exec` → result logged to delta-kernel's timeline.
- **Second consumer:** `services/cortex/src/cortex/clients/uasc_client.py` — Cortex (:3009) also calls the executor.

So the brain/hands split is literal: **delta-kernel decides (governance), uasc-executor does (deterministic, audited), the bridge is the spinal cord.**

---

# PART IV — SYNTHESIS

## 13 · The arc: three tiers of stripping the magic away

The single most important thing about this whole body of work is the **descent from dream to shippable** — the same pattern as ATM → delta-kernel, but here you can watch it happen in three recorded stages:

| Tier | Artifact | Symbol unit | "Intelligence" | Reality |
|---|---|---|---|---|
| **1 · Dream** | `LANGUAGE` corpus | Chinese glyphs, base-9, 7 levels to "all human knowledge" | AI reads holistically, self-expands, invents its own glyphs | a ChatGPT brainstorm |
| **2 · Sober build** | `research/uasc-m2m` reference impl | 16-bit hex opcodes (`@A1`) | none — deterministic graph + authority PKI | working prototype code |
| **3 · Honest ship** | `services/uasc-executor` (:3008) | 7 flat ASCII tokens (`@WORK`) | none — flat lookup + shell/http steps | live, audited, wired to delta-kernel |

Each tier **keeps the load-bearing idea** (*a tiny symbol invokes a whole pre-defined, deterministic, verifiable plan*) and **throws out the magic** (Chinese strokes → opcodes → plain tokens; "AI just knows" → signed registry → flat SQLite lookup). The service's own Origin note says it outright: *"The original vision included stroke-based glyph encoding, neural network interpreters… The practical output was this: a clean command protocol that does one thing well."*

## 14 · It's the same nervous system (again)

This is the `[[atm-vision-delta-kernel-lineage]]` pattern and the `[[user-systems-are-me-shaped-signature]]` signature, one more time:

- **tiny key → full pre-registered plan** (glyph→ExecutionGraph; token→profile) = "pass the key, not the blob."
- **deterministic execution, no generation** (graph walker; sequential steps, capped, audited).
- **signed/verified + append-only audit** (authority PKI in the lab; HMAC + `runs`/`run_events` in the service) = the hash-chain/ledger instinct.
- **brain/hands split** (delta-kernel decides, UASC does) = the same governance-over-execution shape.

UASC is the **execution arm** of the exact engine the ATM/delta-kernel report describes. Same hand, different finger.

## 15 · Open items & recommendations

1. **Two divergent codebases under one name.** The `research/uasc-m2m` reference impl (opcodes + graphs + PKI) and `services/uasc-executor` (tokens + profiles) are *different designs*, not versions of each other. Decide which is canonical, or document that the service is the successor and the lab is archived research. Right now both read as "current."
2. **Footprint cleanup (the mess).** Canonical homes are the 5 in §0. Candidates to consolidate/remove: ~30 `.claude/worktrees/*/research/uasc-m2m` copies, the `pre-atlas` (hyphen) mirror, the **self-nested** `research/uasc-m2m/UASC-M2M/` copy, and the loose zips (`UASC-M2M.zip`, `(1).zip`, `_Bundle_Alpha.zip`, `LANGUAGE.zip` ×2). The `Downloads/LANGUAGE` and `claude-mining/.../LANGUAGE` are duplicate corpora — pick one home.
3. **Lab security (if ever promoted):** placeholder crypto in `trust.py`/`registry.py` (signatures always verify) and the `eval()` condition path in `interpreter.py`. Fine for research, must be replaced before any real authority/trust claim.
4. **Service security note:** `executor.py` runs `subprocess.run(shell=True)` on interpolated profile `cmd`s. It's gated behind HMAC + a 2-client allowlist and profiles are local JSON, so the blast radius is small — but profile inputs flowing into a shell string is worth a guard if untrusted inputs ever reach `/exec`.

---

## Verdict table

| Claim | Verdict | Evidence |
|---|---|---|
| UASC is a 5-layer body (corpus → lab → service → bridge → consumer), not one folder | ✅ | `es` footprint §0; files cited per layer |
| LANGUAGE = a full constructed-language spec (8 docs, 13 sections, 6,874-line origin) | ✅ | `Downloads/LANGUAGE/docs/01-08`, `sections/00-index.md` |
| The built reference impl abandoned Chinese strokes for hex opcodes + signed graphs | ✅ | [glyph.py:31-33](research/uasc-m2m/reference-implementation/core/glyph.py), registry.py, interpreter.py read in full |
| The live service is a flat 7-token profile runner, "the hands," no language/AI | ✅ | [SPEC.md:10-14](services/uasc-executor/SPEC.md), executor.py |
| The service actually ran | ✅ | `output/brief_20260410_*.json` real result files |
| UASC is wired as delta-kernel's execution layer | ✅ (doc-confirmed) | SPEC bridge table + delta-kernel `executor-bridge.ts` + memory; cortex `uasc_client.py` exists |
| Lab crypto is placeholder | ✅ | [trust.py:186-199](research/uasc-m2m/reference-implementation/core/trust.py) "always returns True" |

> **Coverage note (honest):** read first-hand this session — all 8 LANGUAGE `docs/`, the index, and the reference-impl `core/` (glyph/registry/trust/interpreter) in full; the service `SPEC.md`/`executor.py`/`atlas.surface.json`. **Not yet deep-read:** the lab `mvp/` HTTP layer (cli/server/auth), the lab `spec/` 6 docs (they describe the core I read in code), the LANGUAGE `sections/` narrative (the `docs/` are the distilled form), and `server.py`/`auth.py` in the service (the SPEC documents their contract). Say the word and I'll fold any of those in.

