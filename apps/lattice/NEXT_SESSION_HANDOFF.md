# lattice/Atlas · 3-week assemble-first plan

**Status:** Week 1 SHIPPED · Weeks 2-3 NOT started
**Created:** 2026-05-30
**Updated:** 2026-06-25 (reconciled doc to shipped code)
**Project:** Pre Atlas / apps/lattice + services/delta-kernel
**Posture:** compose-from-primitives (per `~/.claude/rules/common/assemble-first.md`)

> **Resume here:** Week 1 (Replicache + Zod sync seam) is live in `index.html`. Do NOT redo it.
> Next session starts at **Week 2 · GO** (cxtmenu/popper/dagre + Zustand). Week 3 (TinyBase) after that.

---

## resume prompt (paste into a fresh chat)

```
Read apps/lattice/NEXT_SESSION_HANDOFF.md. We're executing Week N of the
3-week plan. Current state lives in that file. Don't redo the architecture
pass · the verdict is locked: compose, don't fork. Pick up at "WEEK N · GO".

If you don't know which week to run, check git log + the "verify"
checklist of each week. Resume from the first week whose verify hasn't
passed yet.

Auto-mode rules: bias toward action, use playwright + delta-kernel
direct calls to verify, no hedging, no "tradeoff" framing where one
answer is just better.
```

---

## the verdict (locked · don't relitigate)

**Compose from primitives. Do not fork another app.**

Reason: Logseq, Trilium, SiYuan are all editor-first. Lattice is projection-first (viewmodel over external substrate, no editor). Forking means deleting 60-80% of someone else's code. Composing means building only what's actually mine.

Top 3 forkable repos (for reference only, not the path):
- TriliumNext/Notes · 2.9k★ · TS · AGPL · 8/10 fit
- SiYuan · 44k★ · TS+Go · AGPL · 7/10 fit
- Logseq · 43k★ · TS+CLJS · AGPL · 6/10 fit

---

## current state as of 2026-05-30

### what's running
- `delta-kernel` API on :3001 (TS/Express/SQLite, 6-mode FSM)
- `lattice` frontend on :3011 (single-file HTML + vendored cytoscape.min.js)
- `cognitive-sensor` substrate data at `services/cognitive-sensor/idea_registry.json` (1339 ideas)

### what's hand-rolled (the kill list)
| chunk | location | LOC est |
|---|---|---|
| viewmodel cache + auth token plumbing | `apps/lattice/index.html` `loadViewmodel` + `atlasHeaders` | ~50 |
| optimistic update + rollback (project + status) | `apps/lattice/index.html` `setItemProject`, `setItemStatus`, `postCorrection` | ~80 |
| right-click ctx menu HTML/CSS/JS (project pips + status pills + provenance + toggle) | `apps/lattice/index.html` `openCtxMenu`, `renderCtxMenuBody`, `bindCtxMenuActions` | ~140 |
| settings panel + localStorage state | `apps/lattice/index.html` `settings`, `saveSettings`, `setupSettingsPanel` | ~70 |
| schema validation (typeof checks) | `services/delta-kernel/src/atlas/lattice-projection.ts` `validateCorrection` | ~50 |
| ghost-stub augmentation + BFS over edges | `apps/lattice/index.html` `deriveNodes`, `deriveEdges`, `renderGraph` BFS section | ~100 |
| **total estimated retirement** | | **~490 LOC** |

### what stays (the moat · never touch)
- `services/delta-kernel/src/core/types.ts` 6-mode FSM (RECOVER · CLOSURE · MAINTENANCE · BUILD · COMPOUND · SCALE)
- `services/cognitive-sensor/cluster_leverage_map.py` clustering + leverage scoring
- `contracts/schemas/*.json` all 47 draft-07 schemas
- `services/optogon/` autonomous executor
- `services/cortex/` autonomous execution layer
- `services/perception/` + `services/triangulation/` (Phase A/B stubs)
- `services/cognitive-sensor/lattice_corrections.jsonl` correction → training signal
- the projection RULES in `lattice-projection.ts` (category→project, tier→status mapping)

### what was already swapped (week-0 prep, done)
- ✅ graph rendering: hand-rolled SVG → Cytoscape.js (vendored at `apps/lattice/cytoscape.min.js`)
- ✅ lattice has CORS allowed at :3011 in delta-kernel `server.ts`
- ✅ launch.json has `lattice` entry on :3011

---

## week 1 · sync seam ✅ SHIPPED (2026-06-25)

**Goal:** replace homemade substrate sync + validation with proven primitives.

**Shipped:** Replicache sync seam lives in `index.html:2537-2723` (a `<script type="module">` block) —
custom `customPuller`/`customPusher` over delta-kernel `/api/lattice/viewmodel` + `/api/lattice/correct`,
`ViewmodelZ` Zod schema validating every pull, `correctProject`/`correctStatus` mutators with optimistic
local apply + ack-driven replay. Exposed on `window.latticeSync`. Bearer-token plumbing via
`/api/auth/token` with 401 refresh.

### install (DONE — vendored files present)
```bash
cd apps/lattice
# Replicache vendored as an ESM bundle (NOT replicache.min.js / .umd.js).
# Imported via: import { Replicache, TEST_LICENSE_KEY } from './replicache.bundle.mjs'
#   → apps/lattice/replicache.bundle.mjs

# Zod vendored as UMD, exposed on window.Zod (used as `const z = window.Zod`).
#   → apps/lattice/zod.umd.js  (loaded with a plain <script>, NOT imported)
```

The sync block is `<script type="module">` near the end of `<body>`; it `import`s
`replicache.bundle.mjs` directly. `zod.umd.js` is a classic `<script>` that sets `window.Zod`.

### wire
1. **Define mutators** — for each existing POST `/api/lattice/correct` call, write a Replicache mutator:
   - `correctProject({id, project, originalProject})` mutates local state instantly + queues push
   - `correctStatus({id, status, originalStatus})` same shape
2. **Pull endpoint** — replicache's pull hits `delta-kernel:3001/api/lattice/viewmodel` (already exists, just adapt response)
3. **Push endpoint** — replicache's push posts each queued mutator to `delta-kernel:3001/api/lattice/correct` (already exists)
4. **Zod schemas** — generate from `contracts/schemas/*.json` using `json-schema-to-zod` (run once, vendor output). Validate every viewmodel pull response.

### kill
- Delete `loadViewmodel`, `atlasHeaders`, `fetchAuthToken`
- Delete `setItemProject`, `setItemStatus`, `postCorrection`, `postProjectCorrection`, `postStatusCorrection` (replicache mutators replace them)
- Delete the `try/catch` rollback dance — replicache handles it
- Delete the hand-rolled `validateCorrection` in `lattice-projection.ts` server-side too · replace with Zod parse

### verify (shipped — code present at index.html:2537-2723)
- [x] open lattice → graph view loads with all items (`customPuller` + `rep.pull()` at end of block)
- [x] right-click an item → set project → optimistic update visible (`correctProject` mutator + subscribe rerender)
- [x] kill delta-kernel mid-correction → lattice rolls back automatically (5xx → no ack → Replicache retries/replays)
- [x] reboot delta-kernel → correction re-syncs on reconnect (`pullInterval: 30000` + post-push auto-pull)
- [x] `lattice_corrections.jsonl` still gets the JSONL append (untouched server-side; pusher POSTs to existing `/api/lattice/correct`)
- [~] LOC: net reduction not measured. NOTE: server-side `validateCorrection` was NOT replaced with Zod — only the client gained Zod validation. The hand-rolled `deriveNodes`/`deriveEdges` still exist (1164-1209) — those are Week 3, not Week 1.

### refs
- Replicache: https://replicache.dev
- Zod: https://zod.dev
- json-schema-to-zod: https://github.com/StefanTerdell/json-schema-to-zod

---

## week 2 · view primitives ⛔ NOT STARTED ← resume here

**Goal:** replace hand-rolled ctx menu + settings state with official Cytoscape extensions + Zustand.

**Verified still hand-rolled (2026-06-25):** `openCtxMenu`/`renderCtxMenuBody`/`bindCtxMenuActions`
live at `index.html:2099-2194` (no cxtmenu). None of `cytoscape-cxtmenu`, `cytoscape-popper`,
`cytoscape-dagre`, or `zustand` are vendored in `apps/lattice/`. Settings still use the hand-rolled
`settings` object + `saveSettings` (localStorage) at `index.html:1160`.

### install
```bash
cd apps/lattice
# Official Cytoscape extensions
curl -sL -o cytoscape-cxtmenu.min.js https://unpkg.com/cytoscape-cxtmenu/cytoscape-cxtmenu.js
curl -sL -o cytoscape-popper.min.js https://unpkg.com/cytoscape-popper/cytoscape-popper.umd.js
curl -sL -o cytoscape-dagre.min.js https://unpkg.com/cytoscape-dagre/cytoscape-dagre.js
# Zustand UMD
curl -sL -o zustand.min.js https://unpkg.com/zustand/umd/zustand.production.js
```

Add `<script>` tags + register extensions at startup:
```js
cytoscape.use(cytoscapeCxtmenu);
cytoscape.use(cytoscapePopper);
cytoscape.use(cytoscapeDagre);
```

### wire
1. **cxtmenu** — radial right-click on graph nodes. Replaces our hand-rolled `openCtxMenu`. Commands:
   ```js
   cy.cxtmenu({
     selector: 'node',
     commands: [
       { content: 'set project →', select: () => showProjectPicker() },
       { content: 'set status →', select: () => showStatusPicker() },
       { content: 'show in graph', select: (ele) => recenter(ele.id()) },
       { content: 'delete', select: (ele) => deleteItem(ele.id()) },
     ]
   });
   ```
2. **popper** — provenance tooltips on hover. Replaces the ctx-prov line.
3. **dagre** — give users a "hierarchy" layout choice in the knobs panel (alongside concentric/cose).
4. **Zustand store** for `settings`, `currentView`, `graphCenter`, `currentTimelineSub` · with `persist` middleware (localStorage built in). Replaces `let settings = (function(){...})()`, `saveSettings`, the hand-rolled localStorage read/write.

### kill
- Delete `openCtxMenu`, `closeCtxMenu`, `renderCtxMenuBody`, `bindCtxMenuActions`, `handleCtxAction`, `setupSettingsPanel`
- Delete the `ctx-*` CSS block (kept only what cxtmenu needs)
- Delete the `settings = (function(){...})()` IIFE and `saveSettings`
- Delete the manual `panel.hidden = ...` toggles in `switchView`

### verify
- [ ] right-click a node → radial menu appears (cxtmenu styling)
- [ ] hover a node → provenance tooltip shows (popper)
- [ ] knobs panel still has the same controls but reads from Zustand
- [ ] localStorage still persists across reloads
- [ ] new "hierarchy" layout option in knobs works
- [ ] LOC: net `-200` minimum in `index.html`

### refs
- cytoscape-cxtmenu: https://github.com/cytoscape/cytoscape.js-cxt-menu
- cytoscape-popper: https://github.com/cytoscape/cytoscape.js-popper
- cytoscape-dagre: https://github.com/cytoscape/cytoscape.js-dagre
- Zustand: https://github.com/pmndrs/zustand

---

## week 3 · substrate-side query ⛔ NOT STARTED

**Goal:** replace hand-rolled `deriveNodes` / `deriveEdges` / BFS-over-edges with TinyBase reactive store.

**Verified still hand-rolled (2026-06-25):** `deriveNodes`/`deriveEdges` (incl. ghost-stub augmentation)
live at `index.html:1164-1209`. `tinybase` is not vendored in `apps/lattice/`. NOTE: the Week-1
Replicache `subscribe` snapshot (index.html:2690) now feeds graph state on every pull and does its own
ghost-stub pass — so when this lands, reconcile it with that path, not just the old `deriveNodes`.

### install
```bash
cd apps/lattice
curl -sL -o tinybase.min.js https://unpkg.com/tinybase/umd/index.js
```

### wire
1. **Define a TinyBase store** with tables: `items`, `projects`, `events`, `links`, `nodes`, `edges`
2. **Define indexes** for: items-by-project, links-by-source, links-by-target, nodes-by-depth (relative to focus)
3. **Define queries**:
   - `neighborhood(centerId, depth)` returns `{ nodes, edges }` filtered to graph view
   - `projectGroups()` returns items grouped by project for tree view
   - `eventsByDate()` returns events sorted/grouped for timeline view
4. **Wire replicache → tinybase** — on every pull, hydrate the TinyBase store. Mutators update store reactively.

### kill
- Delete `deriveNodes`, `deriveEdges`, `nodeVisible` helpers
- Delete the BFS loop in `renderGraph`
- Delete the ghost-stub augmentation pass
- The graph render simplifies to: `const { nodes, edges } = store.getQueryResultTable('neighborhood')`
- Tree view: `const groups = store.getQueryResultTable('projectGroups')`
- Timeline view: `const events = store.getQueryResultTable('eventsByDate')`

### verify
- [ ] graph view: same nodes/edges as before, no visual regression
- [ ] tree view: same groupings, sidebar counts match
- [ ] timeline view: ready for events when slice 2 (events projection) lands
- [ ] flipping a knob (depth, project filter, tier) re-renders reactively (no manual `rerenderAll()` calls)
- [ ] LOC: net `-150` minimum in `index.html`

### refs
- TinyBase: https://tinybase.org
- TinyBase queries: https://tinybase.org/api/queries/

---

## kill total: ~500 LOC of homemade plumbing
## moat preserved: 100%

---

## non-goals (do NOT scope-creep into these)

- ❌ event projection from harvest manifests (deferred to slice 4 of original seam plan)
- ❌ status correction backend extension (already done in last session)
- ❌ replacing delta-kernel storage with EdgeDB/Kuzu (substrate is moat, leave it)
- ❌ replacing cognitive-sensor pipeline (moat)
- ❌ rewriting the 47 contracts (just consume them via Zod)
- ❌ moving lattice to React/Vue/Svelte (the single-file shape is fine, plain JS + libs)
- ❌ adding tests beyond playwright smoke (slice 5 territory)

---

## escape hatches

If a primitive turns out wrong-fit mid-week, the fallbacks are:

| primitive | fallback |
|---|---|
| Replicache | RxDB (heavier · larger sync semantics) or TanStack Query (no offline · simpler) |
| Zod | Valibot (smaller bundle · same patterns) |
| cytoscape-cxtmenu | keep hand-rolled ctx menu (don't lose UX) |
| Zustand | nanostores (smaller) or just keep localStorage IIFE |
| TinyBase | keep hand-rolled `deriveNodes` + BFS (it works, just verbose) |

Don't burn a week chasing a primitive that fights you. Fall back, document why, move on.

---

## file pointers (for the next session to grep)

```
apps/lattice/index.html                                       (main edits; W1 sync block at 2537-2723)
apps/lattice/cytoscape.min.js                                 (already vendored)
apps/lattice/replicache.bundle.mjs                            (W1 · vendored ESM, imported)
apps/lattice/zod.umd.js                                       (W1 · vendored UMD, window.Zod)
apps/lattice/[cytoscape-cxtmenu|cytoscape-popper|cytoscape-dagre|zustand].js  (W2 · to vendor)
apps/lattice/tinybase.min.js                                  (W3 · to vendor)
services/delta-kernel/src/atlas/lattice-projection.ts         (backend; W1 trims)
services/delta-kernel/src/api/server.ts                       (CORS + routes; minor)
services/cognitive-sensor/idea_registry.json                  (data source)
services/cognitive-sensor/lattice_corrections.jsonl           (training signal · do not break)
.claude/launch.json                                           (already has lattice + delta-api)
```

---

## origin

Bruke, 2026-05-30, after spending an entire session in piece-by-piece debug mode building a ctx menu, graph layout, settings panel, validation, BFS, optimistic updates by hand. Reframed the build with the "sandwich" metaphor: he wants ham-and-cheese, not to grow wheat and raise pigs. The /jargonize pass named three anti-patterns simultaneously: NIH (Not Invented Here), myopic locality bias, and compositional inversion. The fix codified in `~/.claude/rules/common/assemble-first.md` was being skipped recursively. This plan is the correction.
