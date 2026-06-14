# Pre Atlas — System Shape (Audit Phase 1)

Generated: 2026-05-29. Source: `audit/build_system_index.py` → `audit/system-index.json`.

## A. Subsystems (29 total · 12 in autostart)

### services/ (15)

| Name | Lang | Framework | Port | Auto | Files | LOC |
|---|---|---|---|---|---|---|
| .delta-fabric | unknown | unknown | - | - | 0 | 0 (empty dir / stub) |
| aegis-fabric | ts | express | 3002 | YES | 104 | 15179 |
| canvas-engine | ts | express | 3050 | YES | 78 | 12738 |
| cognitive-sensor | mixed | none | - | no | 386 | 4,319,045 (LOC inflated by .json/db dumps) |
| cortex | py | fastapi | 3009 | YES | 37 | 3952 |
| crucix | js | express | - | no | 74 | 15984 |
| delta-kernel | ts | express | 3001 | YES | 83 | 39809 |
| mirofish | py | fastapi | - | no | 30 | 2933 (Docker-gated) |
| mosaic-dashboard | ts | next | 3000 | YES | 36 | 13897 |
| mosaic-orchestrator | py | fastapi | 3005 | YES | 55 | 7567 |
| openclaw | py | fastapi | 3004 | YES | 22 | 918 |
| optogon | py | fastapi | 3010 | YES | 33 | 4335 |
| perception | py | none | - | no | 18 | 834 |
| triangulation | py | none | - | no | 13 | 1294 |
| uasc-executor | py | none | 3008 | YES | 35 | 3533 (raw http, no framework dep) |
| ws-gateway | ts | none | - | no | 4 | 1011 (NATS-gated) |

### apps/ (7)

| Name | Lang | Framework | Port | Auto | Files | LOC |
|---|---|---|---|---|---|---|
| ai-exec-pipeline | py | flask | - | no | 6 | 507 |
| blueprint-generator | ts | next | 3030 | YES | 33 | 2023 |
| canvas-demo | ts | react | - | no | 7 | 3193 |
| code-converter | py | fastapi | 3007 | YES | 6 | 1500 |
| inpact | ts/html | vanilla | 3006 | YES | 28 | 10979 (static, http-server) |
| lattice | js | vanilla | - | no | 2 | 2403 (single-file SPA + cytoscape) |
| webos-333 | html | vanilla | - | no | 1 | 3442 (single index.html) |

### tools/ (6)

| Name | Lang | Framework | Port | Auto | Files | LOC |
|---|---|---|---|---|---|---|
| anatomy-extension | py+js | vanilla | - | no | 23 | 6684 (Chrome MV3 + sidecar) |
| anatomy-research | mixed | vanilla | - | no | 2694 | 674603 (vendored firecrawl etc.) |
| anatomy-rewrite | unknown | unknown | - | no | 0 | 0 (empty/stub) |
| codex-partner | py | none | - | no | 16 | 458 |
| fest-reconcile | py | none | - | no | 41 | 95538 (LOC inflated by JSON dumps) |
| mini-ship | unknown | unknown | - | no | 0 | 0 (empty/stub) |

**Framework spread (real declared lib):** express 4 · fastapi 6 · next 3 · flask 1 · react 1 (canvas-demo). 15 of 29 subsystems declare a real server framework lib. 6 are "vanilla" (no framework, just HTML/JS). 5 are unknown/none/raw HTTP. 3 are empty stubs.

## B. Spot-check findings

### B1. apps/lattice/index.html — Cytoscape IS loaded (not a hand-roll)

- Single inline `<script>` block: lines 1101–2369 (1,268 LOC of JS).
- External lib: `<script src="cytoscape.min.js">` at line 7 (vendored next to index.html).
- Cytoscape API usage starts at line 1518: `let cy = null; // single Cytoscape instance, lazily initialized`.
- Graph init lines 1672–1694: `cy = cytoscape({…}); cy.add(elements); cy.layout(layoutCfg).run();`.
- Comment at line 1457 acknowledges the choice: `* (d3-force, dagre, or similar).`
- **Verdict:** lattice's graph view delegates to Cytoscape. Memory's "in-memory only · tree/graph/timeline" tag is consistent — tree/timeline are likely hand-rolled DOM, graph is library-backed.

### B2. services/delta-kernel — Mode is hand-rolled string union, transitions are hand-rolled tables

- `src/core/types.ts` is a barrel; real definition lives in `src/core/types-core.ts:50-56`:
  ```ts
  export type Mode =
    | 'RECOVER' | 'CLOSURE' | 'MAINTENANCE'
    | 'BUILD' | 'COMPOUND' | 'SCALE';
  ```
- `xstate` import: ZERO across `src/` and `package.json`.
- Hand-rolled transitions in `src/core/routing.ts:103-146`:
  - `MODE_TRANSITIONS: Record<Mode, RoutingRule[]>` — explicit table per mode.
  - `GLOBAL_OVERRIDES: RoutingRule[]` — preempt routing on sleep/loops signals.
  - Driver: `computeNextMode(currentMode, buckets)` walks overrides → mode rules → fallback stays put.
- **Verdict:** classic functional-table state machine, no library. Pure functions, deterministic. Memory's note on the 6-mode invariant is reflected.

### B3. apps/inpact onboarding — index-based counter, no library

- `onboarding.html` (585 LOC): 4 `<div class="ob-step" id="step-0…3">` panels; CSS toggles `.active` for visibility.
- Navigation: `function goStep(n)` at line 317 — sets/removes `.active` on `#step-N`. Buttons hard-code targets: `onclick="goStep(0|1|2|3)"`.
- No library. No state variable persisted; current step is implicit in DOM (`.ob-step.active`).
- `js/screens.js` (1,236 LOC): different subsystem (main app sidebar router). Uses a `state` object with `state.screen` field + a `stateManager.update({ screen })` call (line 287). Still hand-rolled; routes are a switch over screen IDs.
- **Verdict:** Two flavors of hand-rolled state. Onboarding = DOM-implicit step counter. Main app = object field + manual `stateManager.update`.

## C. Surprises (vs MEMORY.md / inventory.md)

1. **Empty/stub dirs the index surfaced:** `services/.delta-fabric`, `tools/anatomy-rewrite`, `tools/mini-ship` are zero source files. Memory mentions mini-ship as a skill (`~/.claude/skills/mini-ship/`) but `tools/mini-ship/` itself is empty. anatomy-rewrite is listed in memory's "Unrecognized services" note — confirmed empty here.
2. **cognitive-sensor LOC = 4.3M:** dominated by data dumps (.json/.db) counted as "source" by extension. Real Python LOC is much smaller. Indexer would benefit from extension-LOC split if reused.
3. **anatomy-research = 2,694 files / 675k LOC:** mostly vendored upstreams (firecrawl docker-compose etc.). Larger than the entire rest of `tools/` combined.
4. **lattice already uses Cytoscape** — memory's `project_lattice.md` entry doesn't mention any lib; the doctrine premise "hand-rolled SPA" is partially wrong. Graph layer IS library-backed; tree/timeline likely aren't.
5. **uasc-executor (:3008)** runs on raw `python server.py --port 3008` — no framework dep declared (no FastAPI/Flask). Confirmed via index: `framework=unknown`. Matches inventory line `Python/HTTP`.
6. **canvas-demo declared react** but is not autostarted and has no port. Unclear if it's a sandbox or dormant.
7. **crucix** is JS+Express on no port and not autostarted, despite running its own `server.mjs`. Memory says "NOT a scaffold" but it's outside the daemonized fleet.
