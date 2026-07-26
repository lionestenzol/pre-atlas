# Moat Map · Do not touch with libraries

The other side of [swap-backlog.md](swap-backlog.md). These hand-rolls EARN their place: either no library exists, or determinism / doctrine fidelity / tight coupling IS the product. A generic library would make Pre Atlas *worse*, not just *later*.

The "worse vs later" test from [assemble-first.md](../../.claude/rules/common/assemble-first.md) passes for all entries below.

## Confirmed moat

| Subsystem | Why it's moat | A library would make it… |
|---|---|---|
| **delta-kernel 6-mode SEMANTICS** · RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE | Mode meanings ARE Atlas doctrine. No library encodes them. | …meaningless. XState can be the engine; the semantics stay yours. |
| **PNG-Substrate routing** · `services/delta-kernel/src/core/routing-png/`, 220-byte compiled router | Determinism IS the product. The 1458/1458 parity test exists *because* the router can't drift. | …non-deterministic, slower, untrusted. |
| **Routing-PNG dispatch patterns** · c121 LUT, c110 VM, c130 integrity, c140 FSM | Doctrine encoded as bytes. The pattern dictionary IS the product. | …generic, doctrine-blind. |
| **Signal → Atlas state mapping** · cognitive-sensor pattern dictionary (weighted-keyword tracker descended from Ollama-era ancestry) | Doctrine-pattern detection IS the product. | …unable to detect Bruke-specific patterns. |
| **Hash-chain audit trail** · Pre Atlas state history | Custom audit shape, custom guarantee. Not Merkle-standard. | …schema-mismatched, anticorruption layer defeats the point. |
| **Optogon 5-layer stack** · path-runtime architecture | The LAYERING is doctrine. No library encodes "atlas brain stem". | …mis-shaped, would force inversions. |
| **Atlas Directive emitter** · `services/delta-kernel/src/atlas/directive.ts` | Directive grammar IS doctrine. Output contracted with Cortex Ghost Executor + InPACT Signal consumption. | …schema-incompatible. |
| **CycleBoard wiring** · the actuator surface (per `feedback_cycleboard_core.md`) | CycleBoard is core not UI — where governance becomes action. Wiring grammar is doctrine. | …UI-shaped, not actuator-shaped. |
| **Contracts/schemas** · 47 JSON Schema draft-07 contracts | The shape grammar of the system. Bespoke. | …forced into a different schema language. |
| **crucix LLM factory** · `services/crucix/lib/llm/index.mjs` (9-provider factory: Anthropic/OpenAI/OpenRouter/Gemini/Codex/MiniMax/Mistral/Ollama/Grok) | No Node.js library covers all 9 providers including local Ollama at litellm-grade maturity. Factory is 9 lines of provider-select; per-provider glue is domain. Verified Track 2D 2026-05-29. | …force a Python dep (litellm), or drop Ollama, or accept a less-mature Node abstraction. |

## Hybrid — keep doctrine, use library for mechanism

Library underneath, doctrine on top. These are the most leveraged swaps because they preserve moat while killing tax.

| Subsystem | Library does | Doctrine stays yours |
|---|---|---|
| Mode FSM transitions | XState engine + Stately visualizer of YOUR mode graph | 6-mode meanings + guard semantics |
| Background jobs (when needed) | BullMQ / PgBoss as queue | What jobs do, why they fire, audit |
| Vector index | FAISS (already used) | What gets indexed, retrieval scoring weights |
| Embedding model | sentence-transformers MiniLM (already used) | Which conversations to embed, when |
| Validation at boundaries | zod / pydantic (where not already used) | What constitutes valid Atlas state |

## Retired services — NOT moat AND NOT swap targets

From [lava-layers.json](lava-layers.json), six services are retired. Dead code, not products. They are a **cleanup backlog**, not a swap backlog:

- **mirofish** → cognitive-sensor (Neo4j-dep, never autostarted)
- **openclaw** → no clean successor; functionality dispersed
- **mosaic-orchestrator** → optogon
- **blueprint-generator** → canvas-engine
- **mosaic-dashboard** → lattice
- **ai-exec-pipeline** → cortex

Each retired service likely has stale autostart entries, old environment vars, and accumulated config drift. Cleanup pass would: archive the directory, remove from `scripts/start_atlas.ps1`, prune `inventory.md` entries, archive any associated `project_*.md` memory files.

## How to use this map

When proposing a swap from `swap-backlog.md`, cross-check against this map first. If the candidate ALSO appears in moat territory, the swap target is the **mechanism**, not the **semantics**. Examples: swap the FSM library, keep the mode meanings. Swap the queue, keep the job grammar. Swap the JSON parser, keep the schema definitions.

If a swap candidate sits entirely in moat territory (no mechanism/semantics split possible), it's not a swap — it's the product.
