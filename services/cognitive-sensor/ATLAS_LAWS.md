# Atlas Laws

Durable principles that govern how Pre Atlas is organized.
Cite in folder design, code review, doctrine work, and any time the question is "is this organized well?"

---

## Law 1 · Three-Layer Organization (TGT)

> Anything organized in Pre Atlas must have all three layers:
> **TREE** (one home per atom) · **GRAPH** (atoms link to atoms) · **TIME** (when did it happen).

### Why

Without all three, the folder breaks. Every well-organized system — libraries, github, gmail, the brain, the Cognitive Atlas itself — has all three.

- **No TREE** → orphan files. "where did i put it?"
- **No GRAPH** → relationships live in your head, evaporate.
- **No TIME** → can't trust the state, no audit trail.

### How to apply

For any folder, file, doc, dataset, or artifact, ask:

| Layer | Check |
|---|---|
| 🌳 TREE | Does this atom have exactly one canonical home? |
| 🕸️ GRAPH | Is it linkable? Does it reference what it depends on? |
| ⏱️ TIME | Is it timestamped (created / modified / dated)? |

If any layer is missing, the organization is incomplete. **Fix the missing layer before adding UI makeup (dashboards, charts, prettifying).**

### Examples from this repo

| Artifact | TREE | GRAPH | TIME | Verdict |
|---|---|---|---|---|
| `cognitive_atlas.html` | ✓ | ✓ | ✓ | passes |
| `v2/` contaminated docs | ✓ | ✗ | ✓ | rebuild graph |
| `memory_db.json` | ✓ | ✗ | ✓ | needs cross-corpus links |
| Loose `.md` on desktop | ✗ | ✗ | ✗ | orphan; assign home |

### Violation signals (what to listen for)

If you (or anyone working in Pre Atlas) say:

- "where did i put it?" → **TREE** violation
- "i remember they're related" → **GRAPH** violation
- "when did i make this?" → **TIME** violation

The fix is the missing layer, not a new app.

### Origin

Bruke, 2026-05-28. Realization in cognitive_atlas session: apps are folders + makeup. The hard part is the folder, not the makeup. Universal organization shape = TREE + GRAPH + TIME. Without codifying this, future folder work drifts back into "build more apps" instead of "shape the folder."

---

## Law 2 · Assemble First, Don't Generate

> The default build posture in Pre Atlas is **assembler, not generator**.
> When a capability is a solved category, the library option must be named *before* any hand-roll is considered.
> Hand-rolls must earn their place — they are the exception, not the default.

### Why

Pre Atlas has a real moat (mode semantics, PNG-substrate routing, signal→atlas mapping, hash-chain audit). Every hour spent reinventing a solved category — FSMs, graph layout, date math, fuzzy search, validation, queues — is an hour not spent on the moat. Worse, hand-rolled mechanism quietly entangles with doctrine: when the mechanism breaks, the doctrine breaks with it.

- **Reinvention tax** → time + LOC spent rebuilding what `npm install <x>` solves.
- **Mechanism-doctrine entanglement** → bugs in the mechanism corrupt doctrine logic.
- **Drift** → hand-rolls accumulate edge-case patches; libraries get them patched upstream.

### The solved-category test

Before writing any non-trivial implementation, ask: **is this a solved category?**

If yes, the default is **assemble**: check the relevant registry (npm / PyPI / crates.io) + current docs for the mature, maintained package. Surface what you found — name it, note maintenance/adoption, propose it — *before* generating any implementation.

Solved categories include (non-exhaustive): graph layout, drag-and-drop, FSM/statecharts, parsing, date/time, fuzzy search, validation schemas, background jobs, scheduling, virtualized lists, forms, routing, diffing, timelines, ORM, WebSocket, logging, caching, vector search, clustering, text chunking, CLI parsing, TUI. See [assemble-first.md](../../.claude/rules/common/assemble-first.md) for the full reference table.

### The "worse or just later" discriminator

Before hand-rolling, ask out loud:

> "If I use the library instead, will the final product be **worse**, or just **finished sooner**?"

- **Worse** → write it yourself. This is moat.
- **Just sooner** → use the library. This is tax.

If you can't say "the library would make this worse" and mean it, the hand-roll is unjustified.

### How to apply

For any new capability proposed in Pre Atlas, ask:

| Check | Pass condition |
|---|---|
| 🔎 Solved category? | If yes, the library option is named before any implementation skeleton is drafted. |
| ⚖️ Worse-or-later? | "Library would make this worse" can be said out loud and defended. |
| 🪨 Earned? | One of the two earning conditions below is clearly true. |

Hand-rolling earns its place only when **one** of these holds:

1. **No mature option exists** for the capability.
2. **Integration depth is the product value** — the determinism, doctrine fidelity, or tight coupling IS the reason this layer exists, and a generic library would make Pre Atlas *worse*, not just *later*.

If neither is clearly met, the hand-roll is debt that looks stable now and rots over time. **Never present a hand-roll and an established library as peer options.** They are not peers.

### Examples from this repo

| Artifact | Solved category? | Verdict |
|---|---|---|
| `apps/lattice/index.html` graph view (Cytoscape.js vendored) | yes — graph layout | ✓ already assembled |
| `services/canvas-engine` validation (zod + ajv) | yes — schema validation | ✓ already assembled |
| `services/cognitive-sensor` embeddings (sentence-transformers + hdbscan + umap-learn) | yes — embedding / clustering | ✓ already assembled |
| `services/delta-kernel/src/core/types.ts` Mode FSM transitions (hand-rolled) | yes — FSM | ✗ tax — swap engine to xstate, keep mode semantics |
| `apps/inpact/onboarding.html` `goStep(n)` step toggling | yes — FSM / flow | ✗ tax — swap to xstate |
| `services/delta-kernel/src/core/routing-png/` 220-byte compiled router | no — determinism IS the product | ✓ earns moat (condition 2) |
| `services/delta-kernel/src/atlas/directive.ts` Directive emitter | no — doctrine grammar | ✓ earns moat (condition 2) |
| Hash-chain audit trail | no — custom guarantee, not Merkle-standard | ✓ earns moat (condition 1+2) |

See [audit/swap-backlog.md](../../audit/swap-backlog.md) for the active tax-pay list and [audit/moat-map.md](../../audit/moat-map.md) for the full earned-hand-roll registry.

### Violation signals (what to listen for)

If you (or anyone working in Pre Atlas) say:

- "I'll just write a quick FSM / parser / date-helper" → **solved-category violation**
- "it's only ~150 lines, library is overkill" → **discriminator violation** (sooner ≠ worse)
- "we have <library A> and a hand-roll, pick one" → **false-symmetry violation**
- "we'll come back and swap it later" → **debt-laundering signal** (later rarely comes)

The fix is to name the library, run the worse-or-later test, and only hand-roll if one of the two earning conditions clearly holds.

### Origin

Bruke, 2026-05-29. Triggered by a lattice-graph build session where Claude started hand-rolling SVG node-link rendering. Pushback: *"do we need to code a graph isnt there graph software or code that already exists."* Cytoscape.js was the answer. The subsequent dogfood audit on Pre Atlas confirmed the pattern as systemic (delta-kernel Mode FSM, inPACT step-toggling) but *also* confirmed the instinct was already firing in places (lattice had vendored Cytoscape before the doctrine was named). This law names the pattern so it fires consistently — and so future builds in Pre Atlas spend reinvention budget only on the moat.

Cross-reference: [[feedback_assemble_first_posture]] · global rule at `~/.claude/rules/common/assemble-first.md`.

---

## Adding new laws

When a new principle earns "law" status:

1. Append a new section here as `## Law N · <Name>`.
2. Include: principle (one sentence), why, how to apply, examples, violation signals, origin.
3. Cross-reference with a `[[memory-slug]]` in the matching memory file.
