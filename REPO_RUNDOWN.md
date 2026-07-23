# Pre Atlas — Full Repo Rundown

> **Single source of truth.** One human-readable + LLM-ingestible map of the whole
> repo. Generated 2026-06-22 by reconciling three independent inventories:
> a deterministic file/LOC scan (`repo-inventory`), `audit/system-index.json`
> (ports/frameworks/autostart), and `atlas-map.json` (purposes/edges/governance).
> Where the tools disagreed, the discrepancy is resolved and noted — see
> **§7 Reconciliation**. Counting is done by code, not by eye: same repo in,
> same numbers out.

---

## 1. What this repo is (one paragraph)

**Pre Atlas is a personal behavioral-governance system built as a federated
monorepo.** A deterministic TypeScript state engine (`delta-kernel`) is the hub;
everything else is a spoke that reads from it or writes signals back to it over
one-way HTTP seams. A Python analysis pipeline (`cognitive-sensor`) turns
conversation history into state (ideas, loops, metrics); a set of autonomous
executors (`cortex`, `optogon`, `droplist`) can act on that state behind
default-off gates; and a handful of UIs (`inpact`, `lattice`, dashboards)
project the state for a human. The architecture is **hub-and-spoke over SQLite +
HTTP**, *not* an event bus — most "pipelines" are reads, and most automation is
dormant or gated off by design.

---

## 2. The numbers (trusted, reconciled)

| Scope | Files | Code LOC | Note |
|---|--:|--:|---|
| **Whole tree (raw)** | 8,428 | 904,772 | what a naive scan reports |
| **− vendored** (`tools/anatomy-research`) | −2,967 | −574,730 | 3rd-party R&D, not yours |
| **− build output** (`canvas-engine/dist` etc.) | ~−2,000 | ~−28,000 | generated, not source |
| **≈ Code you own** | **~3,400** | **~302,000** | the real surface |

**Distribution of owned code:** `services/` ≈ 242K LOC (19 systems) ·
`apps/` ≈ 30K LOC (7 UIs) · `tools/`, `scripts/`, `doctrine/`, `audit/` ≈ 30K ·
the rest is contracts, data, and docs.

> ⚠️ **`cognitive-sensor` reports 116K "LOC" but is ~half JSON state dumps**
> (e.g. `timeline_events.json` is 2.2 MB). Its actual Python source is a small
> fraction of that. Treat it as a *data store with a pipeline*, not 116K lines
> of logic.

---

## 3. System catalog — `services/` (19 systems, the engine room)

Legend: **port** · **fw**=framework · **auto**=starts on boot · LOC=owned source.

| System | Purpose | Lang | Port | Auto | LOC |
|---|---|---|--:|:--:|--:|
| **delta-kernel** ⭐ | Deterministic state engine · 6-mode FSM · **the API hub** | TS/express | 3001 | ✅ | 35,043 |
| **cognitive-sensor** | Conversation-analysis pipeline · idea registry · state store | Py/fastapi | — | — | ~116K* |
| **aegis-fabric** | Admin gateway · API middleware · policy/approval | TS/express | 3002 | ✅ | 12,378 |
| **droplist** | Capture → packet → DAG execution engine | Py/fastapi | 3073 | on-demand | 9,151 |
| **mosaic-orchestrator** | FastAPI orchestrator *(legacy)* | Py/fastapi | — | ✅ | 7,578 |
| **canvas-engine** | URL → live React clone via in-process Vite pool | TS/express | 3060 | ✅ | 7,001 |
| **cortex** | Autonomous execution layer (gated) | Py/fastapi | — | ✅ | 3,952 |
| **optogon** | Autonomous executor · preference seeding · signal emission | Py/fastapi | 3010 | ✅ | 3,949 |
| **search-stack** | Router over 28 search providers | Py/fastapi | 3070 | — | 3,376 |
| **mirofish** | Prediction engine (neo4j-dep) *(legacy)* | Py/fastapi | — | — | 2,933 |
| **uasc-executor** | UASC command executor · HMAC auth | Py | 3008 | ✅ | 2,248 |
| **mosaic-dashboard** | Next.js dashboard *(legacy)* | TS/next | 3000 | ✅ | 2,137 |
| **atlas-map-api** | GPS substrate API (the map behind this doc) | Py/fastapi | 3072 | — | 2,085 |
| **crucix** | Dashboard server ("jarvis") | HTML/express | — | — | 1,951 |
| **triangulation** | Phase B stub (never launched) | Py/fastapi | — | — | 1,294 |
| **openclaw** | FastAPI service *(legacy)* | Py/fastapi | — | ✅ | 918 |
| **perception** | Phase A stub | Py | — | — | 832 |
| **memory-hub** | Memory aggregation | Py/fastapi | 3071 | — | 558 |
| **ws-gateway** | WebSocket gateway (NATS↔socket.io) | TS | 3006 | — | 122 |

\* cognitive-sensor LOC is data-inflated — see §2.
Ports above are the **runtime** ports from `.claude/launch.json` (the boot truth),
which differ from `system-index.json` in 3 places — see §7.

---

## 4. System catalog — `apps/` (7 UIs, the human surface)

| App | Purpose | Lang | Auto | LOC |
|---|---|---|:--:|--:|
| **lattice** | Viewmodel projection · tree/graph/timeline (vendors Cytoscape) | JS | — | 12,506 |
| **inpact** | Daily-flow UI · onboarding · cycleboard | JS | ✅ | 11,066 |
| **webos-333** | Experimental | HTML | — | 3,442 |
| **code-converter** | Python → C++ converter · AST engine | Py/fastapi | ✅ | 1,254 |
| **blueprint-generator** | Next.js blueprint UI *(legacy)* | JS/next | ✅ | 979 |
| **ai-exec-pipeline** | AI execution pipeline *(legacy)* | Py/flask | — | 455 |
| **canvas-demo** | Programmatic Remotion vs dummy site | TS/react | — | 254 |

---

## 5. System catalog — `tools/` (owned only; vendored excluded)

| Tool | Purpose | LOC |
|---|---|--:|
| **anatomy-extension** | Chrome MV3 anatomy-capture extension | 5,293 |
| **fest-reconcile** | Festival manifest reconciler | 3,169 |
| **atlas-cli** | `atlas where/locate/path/...` CLI over the map | 627 |
| **atlas-audit** | Audit pipeline & system-index generator | 236 |
| **codex-partner** | Codex companion tooling | 211 |
| ~~anatomy-research~~ | **VENDORED 3rd-party** (574K LOC) — not your code | — |

---

## 6. How it connects (the seams)

**Hub-and-spoke. `delta-kernel` is the center.** Edges are one-way HTTP reads or
signal writes (from `atlas-map.json` service_edges):

```
                         ┌──────────────────────────┐
   lattice ───────────▶  │                          │
   inpact ────────────▶  │                          │  ◀──── cognitive-sensor
   droplist ──────────▶  │       delta-kernel       │  ◀──── canvas-engine ◀── crucix
   cortex ◀── optogon ▶  │   (deterministic hub)    │  ◀──── code-converter
   aegis-fabric ──────▶  │      state · 6-mode      │  ◀──── ws-gateway
   uasc-executor ─────▶  │          FSM             │  ◀──── cognitive-sensor
                         └──────────────────────────┘
   droplist ──▶ search-stack        perception ──▶ triangulation
   lattice  ──▶ cognitive-sensor    mosaic-dashboard ──▶ mosaic-orchestrator ──▶ optogon
   inpact   ──▶ cortex
```

**The 6-mode FSM** (delta-kernel's core):
`RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE`

**The spine loop** (capture → act → reflect):
`cognitive-sensor` (analyze) → `optogon`/`cortex` (propose/execute, gated) →
`droplist` (packetize) → `delta-kernel` (commit state) → `lattice`/`inpact` (project).

**Contracts** govern every seam: `contracts/schemas/` holds **50 JSON-Schema
(draft-07) data contracts** — `Signal.v1`, `Directive.v1`, `TaskPrompt.v1`,
`BuildOutput.v1`, `CloseSignal.v1`, `AtlasArtifact.v1`, the 7 `Aegis*` contracts,
and the state-store schemas. These are the typed wire format between systems.

---

## 7. Reconciliation (why prior counts were a mess)

The "mixed results" you hit came from **three real causes**, now resolved:

1. **Vendored code counted as yours.** `tools/anatomy-research` is 574,730 LOC —
   **63% of the entire repo** — but it's 3rd-party R&D. Every tool that counted
   it made the repo look 3× bigger than it is. *Fix: exclude it from "owned."*
2. **Build output counted as source.** `canvas-engine` shows 35K LOC / 2045 files
   in a raw scan but only **7K LOC / 71 files of real source** — the rest is
   `dist/` and partial nested deps. *Fix: trust the source count (71 files).*
3. **Data dumps counted as code.** `cognitive-sensor`'s 116K "LOC" is heavily
   JSON state (multi-MB files). *Fix: flagged inline; treat as data store.*

**Cross-tool agreement after fixes:** `delta-kernel` 35,043 LOC (exact match,
3/3 tools) · system count = **35 systems** (19 services + 7 apps + 9 tools),
matches `system-index.json` `subsystem_count: 35`.

**Open hygiene flags:**
- **`system-index.json` port drift (verified against `.claude/launch.json`):** the
  audit generator reads code-level defaults, not the runtime launch ports, so it's
  wrong in 3 places — it lists `optogon` port as `null` (actually **3010**, the
  runtime owner; `cortex` + `cognitive-sensor` both hard-point there), `aegis-fabric`
  as `3010` (actually **3002**), and `triangulation` as `3010` (a stub that never
  launches). **No actual runtime collision exists.** Fix belongs in the audit
  generator (`tools/atlas-audit`), not the JSON — hand-editing would just re-drift.
- **Latent port footgun (not active):** `aegis-fabric`'s gateway sub-package
  (`packages/gateway/src/server.ts`) and `triangulation`'s config both default to
  **3010**, which optogon owns at runtime. Harmless today (neither runs on its
  default), but a trap if either is ever started standalone. Cheapest hardening:
  change the two stale defaults to free ports (gateway→3002 to match its real
  allocation, triangulation→3013) so defaults can never clash with optogon.
- **Lifecycle drift:** 6 systems tagged `retired` in `atlas-map.json` but still
  present & some still `in_autostart`: `mirofish`, `openclaw`, `mosaic-dashboard`,
  `mosaic-orchestrator`, `blueprint-generator`, `ai-exec-pipeline`.

---

## 8. Automation state (what actually runs)

From `atlas-map.json` governance — **most automation is off by design**:

| System | State | Detail |
|---|---|---|
| delta-kernel | 🟢 **active** | governance daemon, 9 cron jobs, */5 heartbeat |
| droplist | 🟡 on-demand | drop→packet→DAG, not auto-scheduled |
| cortex | 🔴 **gated** | acts only if `CORTEX_BRIDGE_APPLY=1` (default off) |
| optogon | 🔴 **gated** | writes back only if `AUTO_TRIAGE_APPLY=1` (default off) |
| cognitive-sensor | ⚪ **dormant** | triage arm unscheduled; hand-cranked via `at` |

**12 of 35 systems** are flagged `in_autostart`. The rest are manual.

---

## 9. Lifecycle tags

- **New since last audit:** `droplist`, `memory-hub`, `search-stack`,
  `atlas-audit`, `reminders`
- **Retired** (candidates for deletion — see §7 drift flag): `mirofish`,
  `openclaw`, `mosaic-dashboard`, `mosaic-orchestrator`, `blueprint-generator`,
  `ai-exec-pipeline`

---

## 10. For the LLM ingesting this

If you're an assistant being handed this file as context, know:
- **`delta-kernel` (port 3001) is the hub.** When in doubt about where state
  lives, it's there (SQLite, better-sqlite3).
- **Seams are one-way HTTP + JSON-Schema contracts**, not shared DBs or an event
  bus. To trace data flow, follow `contracts/schemas/*.v1.json`.
- **"Legacy"/"retired"/"stub" tags are load-bearing** — don't propose building
  on `mosaic-*`, `mirofish`, `openclaw`, `perception`, or `triangulation`.
- **Automation is gated off on purpose.** Don't assume `cortex`/`optogon` act
  autonomously; they need explicit env flags.
- **Ignore `tools/anatomy-research/`** — it's vendored, not the product.
- Authoritative machine-readable sources: `audit/system-index.json` (counts/ports),
  `atlas-map.json` (purposes/edges/governance), `contracts/schemas/` (wire format).
```
