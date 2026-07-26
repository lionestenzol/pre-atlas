# Atlas × ATM × UASC — the three-way analysis

> **What this is.** The analysis the [prep doc](ATLAS_ATM_UASC_PREP.md) loaded the chamber for. Three systems compared on 6 axes, each grounded in primary source (delta-kernel core types, atlas-manifest.yaml, the ATM map's file-receipts, the UASC report's code reads). The prep doc flagged "no clean Atlas doc" as the blocker — §1 below closes that gap inline, then §2-§5 run the comparison.
> **Date:** 2026-06-28. **Method:** first-hand from source; no agents. **Companion docs:** [GEMINI_ATM_MAP.md](GEMINI_ATM_MAP.md) · [UASC_LANGUAGE_REPORT.md](UASC_LANGUAGE_REPORT.md).

---

## TL;DR (the thesis, one paragraph)

These are not three projects. They are **one architectural instinct expressed against three domains.** The instinct: *a tiny, verifiable key unfolds deterministically into a whole pre-registered plan; nothing is mutated, everything is appended and audited, and no intelligence is generated at runtime.* Point that engine **inward at one life** and you get **Atlas** (governance, shipped). Scale it **outward across a town** and you get **ATM** (transport, dreamed — only the engine is built). Give it **an arm to act in the world** and you get **UASC-executor** (execution, shipped and wired). The hub where all three physically meet is **delta-kernel** — and the relationships are three different *kinds*: Atlas *is* delta-kernel's core, ATM *is* delta-kernel scaled out, UASC-executor *bolts onto* delta-kernel as its hands. The tell that confirms it's one mind: every time the dream meets the build, **the exact same magic gets stripped** — emergent/generative "intelligence" — and the exact same skeleton survives — deterministic replay of signed deltas.

---

## 1 · ATLAS, clean (closing the prep-doc gap)

The one system of the three that is **fully real and running.** Synthesized from `delta-kernel` source + `atlas-manifest.yaml` + memory.

- **What it is.** A personal behavioral-governance OS — a federated monorepo that governs *Bruke's life* the way an OS governs a machine. 22 systems, ~253k owned LOC, 50 JSON-Schema contracts ([atlas-manifest.yaml:32](atlas-manifest.yaml:32)).
- **The hub.** `delta-kernel` (:3001) — a deterministic state engine. The manifest names it the hub explicitly ([atlas-manifest.yaml:22](atlas-manifest.yaml:22)). Architecture: **hub-and-spoke over SQLite + one-way HTTP seams; JSON-Schema contracts are the wire format. NOT an event bus** ([atlas-manifest.yaml:21](atlas-manifest.yaml:21)).
- **The unit.** The **Delta** — `interface Delta { … prev_hash: SHA256; new_hash: SHA256; }` over state carrying a `current_hash` ([types-core.ts:75-86](services/delta-kernel/src/core/types-core.ts:75)). Every state change is an appended, hash-chained fact. This is the Sundial, on one node.
- **The clock.** A 6-mode FSM: `RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE` ([atlas-manifest.yaml:23-29](atlas-manifest.yaml:23), [types-core.ts:50](services/delta-kernel/src/core/types-core.ts:50)). Mode transitions are `MODE_CHANGED` events on the append-only timeline.
- **The spine loop.** `cognitive-sensor (analyze) → optogon/cortex (propose/execute, gated) → droplist (packetize) → delta-kernel (commit state) → lattice/inpact (project)` ([atlas-manifest.yaml:36](atlas-manifest.yaml:36)). Sensors propose; only delta-kernel commits.
- **The hands.** `uasc-executor` (:3008) — see §UASC. The brain decides; the hands do.

**Atlas in one line:** the deterministic event-sourced engine, *pointed at a single human life.*

---

## 2 · The six-axis comparison

| Axis | ATLAS (governance) | ATM (transport) | UASC (language/execution) |
|---|---|---|---|
| **1 · Domain** (what it acts on) | governs **a life** | moves **data** across a town | expresses & executes **commands** |
| **2 · The unit** (tiny→whole) | the **Delta** (`prev_hash→new_hash`) + Mode | the **Seed/Key** over the Sundial | the **Glyph→ExecutionGraph** (lab) / **Token→Profile** (service) |
| **3 · Brain vs hands** | the **brain** — decides, holds state | the would-be **nervous system** — transport (mostly unbuilt) | the **hands** — does, deterministic, audited |
| **4 · Dream→build→ship tier** | **shipped & running** (tier 3; dream is implicit) | **dream + engine only** (tiers 1+2; tier-3 city layer hits a hardware wall) | **all 3 tiers preserved as separate artifacts** on disk |
| **5 · Shared signature** | 4 of 5 (drops self-expansion) | 5 of 5 (dream tier) | 5 of 5 in the dream, 4 of 5 in the build |
| **6 · Topology** | **IS** delta-kernel's core | **IS** delta-kernel scaled out | **BOLTS ONTO** delta-kernel as its arm |

### Axis 2 — the unit is the whole signature in miniature
All three units are the same shape: **a tiny addressable token that unfolds deterministically, from a pre-registered home, into a complete plan or state.** "Pass the key, not the blob."
- Atlas: a Delta is an address into the hash chain; folding deltas reconstructs state (`State(T) = Fold(InitialState, Events₀→T)` — identical in the ATM map's Part 2.1 and delta-kernel's `delta.ts`).
- ATM: a Seed regenerates content locally (procedural generation); the glyph 道 is claimed to hold "all human knowledge."
- UASC: the glyph "**contains nothing** — its code is *bound* to a pre-registered ExecutionGraph in a Registry; the opcode is just an address" ([UASC report §8](UASC_LANGUAGE_REPORT.md), citing `glyph.py`/`registry.py`). The token `@WORK` is a key into a JSON profile.

This is the deepest structural rhyme: **glyph→graph is to UASC what delta→state is to Atlas what seed→content is to ATM.** One idea, three notations.

### Axis 3 — brain/hands is literal and wired, not metaphor
`delta-kernel/src/core/executor-bridge.ts` maps `ActionType → token` (`complete_task→@CLOSE_LOOP`, `apply_automation→@WORK`…), signs HMAC, POSTs to `:3008/exec`. uasc-executor's own SPEC: *"It is the 'hands' of the system. It does not decide what to do. **Delta-kernel decides.**"* The bridge is the spinal cord. ATM's "nervous system" (the Data-Mule mesh, the Sun) is the one of the three bodies that stays mostly unbuilt.

### Axis 4 — UASC is the Rosetta Stone for *how Bruke ships*
The three differ most in how much of the dream→build descent is *visible*:
- **ATM** shows you the dream in full (the 218K-char adversarial spec) and the engine as built (delta-kernel), with a **gap in the middle** that is hardware/human-coordination, not software.
- **Atlas** shows you only **tier 3** — the running product. The dream is internal; you don't see it unless you read the lineage doc.
- **UASC** is the only system where **all three tiers sit on disk as separate, diffable artifacts**: the `LANGUAGE` corpus (Chinese glyphs, base-9, 道 = all knowledge) → the reference impl (16-bit hex opcodes + signed ExecutionGraphs + authority PKI) → `uasc-executor` (7 flat ASCII tokens + JSON profiles + shell/http/log steps). You can literally watch the magic get stripped twice. **If you want to understand the move that produced Atlas and delta-kernel, read UASC — it's the recorded version of the same surgery.**

---

## 3 · The shared-signature test (the sharpest finding)

The prep doc named 5 signature elements. Tested against every *shipped* artifact, **4 survive universally and exactly 1 is always stripped.**

| Signature element | Atlas | ATM (dream) | ATM (engine=delta-kernel) | UASC (dream/LANGUAGE) | UASC (build/service) | Survives the build? |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **Time-as-storage / append-only** | ✅ delta hash chain, timeline-logger | ✅ the Sundial | ✅ `delta.ts` | ✅ master log | ✅ `runs`/`run_events` SQLite | **always** |
| **Determinism over generation** | ✅ deterministic engine | ✅ "simulating the computer computing" | ✅ deterministic replay | ⚠️ "AI reads holistically" | ✅ flat lookup, no AI | **always (after stripping)** |
| **Compression-to-essence** (key not blob) | ✅ `delta-sync`: "No blobs" | ✅ seeds not videos | ✅ 220-byte LoRa cap | ✅ 道 = one glyph | ✅ token→profile | **always** |
| **Trust + audit** | ✅ hash-chain verify, contracts | ✅ authority PKI, aBFT | ✅ hash chain | ✅ obfuscation + auth | ✅ HMAC + audit ledger | **always** (crypto stubbed in lab) |
| **Self-expansion** | ❌ fixed modes, curated | ✅ homeostasis, federated distillation | ⚠️ no | ✅ AI generates its own glyphs | ❌ 7 frozen tokens | **never** |

**The finding:** *self-expansion is the consistently-stripped element.* It is the most romantic of the five (the network learns; the language grows itself; the AI invents glyphs), and it is the one that never survives contact with a shippable build. ATM keeps it only in the dream tier; UASC explicitly kills it (the reference impl is "a deterministic graph interpreter… nothing is inferred"); Atlas was *born sober* and never had it — its modes are a fixed enum, expansion happens by a human adding a contract, not by emergence.

This is the same surgery in all three: **the magic that gets cut is always emergent/generative intelligence; the skeleton that survives is always deterministic replay of signed deltas.** The shipped systems are the dream with the AI removed and the audit log kept.

---

## 4 · Connection topology — the hypothesis, proven and sharpened

**Prep-doc hypothesis:** *delta-kernel is the hub; ATM/UASC/Atlas are three faces of one event-sourced spine.*

**Verdict: CONFIRMED — but "three faces of a spine" undersells it, because the three relationships are different *kinds*, not symmetric faces.**

```
                    ┌─────────────────────────────┐
                    │   delta-kernel  (:3001)      │
                    │   the deterministic,         │
                    │   event-sourced ENGINE       │
                    │   — Delta = prev→new hash    │
                    └─────────────────────────────┘
                       ▲            ▲            ▲
        IDENTITY ──────┘    ANCESTRY│   COMPOSITION└────── (HMAC bridge)
        (it IS the core)            │     (bolted-on arm)
                                    │
   ┌──────────────┐    ┌────────────────────────┐    ┌──────────────────┐
   │   ATLAS      │    │   ATM                   │    │  uasc-executor   │
   │ engine       │    │ engine scaled OUT       │    │ engine's HANDS   │
   │ pointed IN   │    │ across a town           │    │ (:3008)          │
   │ at one life  │    │ (city layer UNBUILT)    │    │ token→profile    │
   │ [BUILT]      │    │ [DREAM + engine only]   │    │ [BUILT + wired]  │
   └──────────────┘    └────────────────────────┘    └──────────────────┘
        governance            transport                   execution
```

- **Atlas ⟷ delta-kernel = IDENTITY.** delta-kernel isn't *connected to* Atlas; the manifest names it Atlas's hub. Atlas is what the engine *is for*.
- **ATM ⟷ delta-kernel = ANCESTRY / SCOPING.** Per the ATM map's receipts (read first-hand: `delta.ts` hash chain, `delta-sync.ts`'s `DEFAULT_MAX_PACKET_BYTES = 220 // LoRa-safe`, the 6-mode FSM as "the clock"), **delta-kernel is ATM-minus-the-hardware, running on one node.** ATM is the engine scaled *out*; Atlas is the same engine pointed *in*. The software was never the wall — the hardware/human-coordination layer is.
- **UASC ⟷ delta-kernel = COMPOSITION.** `uasc-executor` is a separate running process the brain commands through `executor-bridge.ts`. It's a limb, not the trunk.

**The cleaner statement than "three faces":** delta-kernel is one engine, and Atlas / ATM / UASC are **three operations you can perform with it** — point it inward (govern), scale it outward (transport), give it an arm (execute). Two of the three are built; the third (ATM at scale) is the one blocked on atoms, not code.

---

## 5 · The essence (one line)

> **delta-kernel is the heart; Atlas is the heart governing a life, ATM is the heart networking a town, UASC is the heart's hand reaching into the world — and the reason they rhyme is that they are literally the same heart, with the same magic (emergent intelligence) cut out and the same skeleton (signed, append-only, deterministic deltas) kept.**

ATM = how things *move*. UASC = how things are *said* and *done*. Atlas = how things are *governed*. One deterministic, event-sourced spine, wearing three domains.

---

## Verdict table

| Claim | Verdict | Evidence |
|---|---|---|
| delta-kernel is Atlas's hub (identity, not connection) | ✅ | [atlas-manifest.yaml:22](atlas-manifest.yaml:22) `hub: delta-kernel` |
| The Atlas unit is an append-only hash-chained Delta | ✅ | [types-core.ts:79-86](services/delta-kernel/src/core/types-core.ts:79) |
| delta-kernel is ATM scoped to one node (ancestry) | ✅ | ATM map §"delta-kernel IS this system, scoped down"; `delta-sync.ts` 220-byte LoRa cap, `delta.ts` hash chain — read first-hand |
| uasc-executor is delta-kernel's wired execution arm (composition) | ✅ | `executor-bridge.ts` ActionType→token + HMAC→:3008; uasc SPEC "delta-kernel decides" |
| All three units share one shape (key→pre-registered plan) | ✅ | Delta→state · Seed→content · Glyph→ExecutionGraph / Token→Profile |
| Self-expansion is the one signature element always stripped at ship | ✅ | Atlas fixed modes; UASC reference impl "nothing is inferred"; ATM keeps it only in dream tier |
| The hub hypothesis ("three faces of a spine") | ✅ confirmed, sharpened to **three operations on one engine** | §4 topology |

> **Coverage note (honest):** Atlas grounded in `types-core.ts` + `atlas-manifest.yaml` head + memory; full delta-kernel module-by-module read not re-run this session (the ATM map already did it and is cited). UASC rests on the prior first-hand report; its flagged-skipped files (lab `mvp/`, `spec/`, LANGUAGE `sections/`, service `server.py`/`auth.py`) remain un-deep-read and are not load-bearing for this comparison. ATM rests on the verified map + transcript. No claim here depends on an unread file.
