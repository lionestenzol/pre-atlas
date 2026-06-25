# Scraper Pipeline Audit · Pre Atlas Conversion-Intelligence Wedge

**Scope** · `tools/anatomy-extension` (the actual scraper, browser-side parser) + `services/canvas-engine` (variant generator, downstream) + `tools/anatomy-rewrite` and `tools/anatomy-research` (specs + reference archive) + `contracts/schemas/AnatomyV1.v1.json` (the gluing contract).
**Mode** · Static analysis only. Nothing was executed. No live URLs hit.
**Date** · 2026-04-26
**Read-from** · main repo (`C:/Users/bruke/Pre Atlas/`); the worktree's `tools/anatomy-extension/` only ships `content.js`, the rest of the extension lives untracked in main.

---

## Context

You're building a conversion-intelligence engine. The wedge: pull a winning page → map its structure → identify the conversion logic → generate deployable variants → track the winner. Compounding asset = a pattern library of component-level conversion data segmented by category, vertical, recency.

What exists today, in pipeline order:

```
[browser tab]
   │  user opens a page, Alt+clicks, dwells
   ▼
tools/anatomy-extension  (Chrome MV3, vanilla JS, ~3,800 LOC of in-browser code)
   │  pulls DOM + canvases + intercepts fetch/XHR via page-world.js
   │  parses cascade rules r2-r12 → regions[]
   │  emits AnatomyV1 envelope (anatomy.json)
   ▼
chrome.storage.local  +  POST localhost:8088/ingest  (daemon dev only)
   │
   ▼
services/canvas-engine  (TS, Express, Vite, ~44 src files, port 3050)
   │  SitepullResolver discovers anatomy.json by host
   │  zod-validates envelope against AnatomyV1
   │  pattern-library picks component templates per region (23 patterns / 8 groups)
   │  generates App.jsx + Component.jsx files
   │  spawns a Vite sandbox (port pool 3060-3069, mkdtemp dir)
   │  serves live editable React clone via SSE
   │  /edit endpoint applies deterministic transforms (tint / rename / hide / note)
```

Two adjacent dirs hold the strategy and reference work but are not on the runtime path:
- `tools/anatomy-rewrite/` — Plan D clean-room SPECs (3 specs · 1 protocol · 1 harness · 1 test corpus). No code yet.
- `tools/anatomy-research/` — locked 2026-04-22 archive · 170 MB · vendored `browser-use`, `firecrawl`, `JSON-Alexander`, `json-render`, `firecrawl-mcp-server` + `plan-d-signal/` probes.

Net: the runtime pipeline is two real components (extension + canvas-engine), bound by one schema (AnatomyV1.v1.json), with two reference dirs on the side. The extension does the scraping; canvas-engine does the variant generation. Bruke's "scraper" question maps cleanly to the extension as the first stage. The audit treats the whole stack as one pipeline.

---

## 1 · Architecture map

### 1a · `tools/anatomy-extension` (the scraper)

Chrome MV3, vanilla JS, no bundler. Lives in main repo; **most of the directory is git-untracked** (memory entry confirmed). The worktree only carries the modified `content.js`.

```
tools/anatomy-extension/
├── manifest.json              MV3, v0.4.4, host_permissions: <all_urls>
├── background.js              Service worker · fetch relay · /dev/version hot-reload
├── popup.html · popup.js      Status / toggle / export / clear UI
├── content.js                 ~2,700 LOC · isolated world · the labeling engine
├── page-world.js              MAIN world · patches fetch + XHR · emits anatomy:request
├── content.css                HUD + tag styling
├── lib/
│   ├── detection-vocab.js     Closed vocab · TWO-WAY CONTRACT with canvas-engine
│   ├── canvas-precapture.js   Canvas → data-URL · 10 MB cap, taint-safe
│   ├── adopted-stylesheets.js Plan D Spec 01
│   ├── shadow-dom-recursion.js Plan D Spec 02
│   ├── runtime-inline-styles.js
│   └── text-grid.js           Prominence-grid scoring (auto-label tiebreaker)
├── dev-tools/                 Python verifiers · cascade miners · headless calibration
├── calibration/               Headless-playwright score harness (was 93% on grid)
├── ANATOMY_V1_SCHEMA.md       Markdown spec, narrative twin of the JSON schema
└── README.md
```

**MV3 worlds split.** Three execution contexts (text, not pictograms):

| World | File | Runs at | Job |
|---|---|---|---|
| MAIN (page) | `page-world.js` | `document_start` | Patch `window.fetch` + `XHR.open/send` · emit `anatomy:request` CustomEvent |
| ISOLATED (content) | `content.js` + `lib/*` | `document_idle` | DOM walk, label, store, render HUD, emit envelope |
| Service worker | `background.js` | persistent | Cross-origin fetch relay · daemon ping · hot-reload poll |

Message flow · page-world dispatches CustomEvents → content.js subscribes → optional POST through background.js to localhost:8088. Popup talks to content.js via `chrome.tabs.sendMessage`.

### 1b · `services/canvas-engine` (variant generator)

TypeScript, Express 5.2, Vite 5.4, Zod, React 18, Tailwind. No bundler for runtime — `tsx watch` in dev. Listens on `:3050`, allocates Vite sandboxes from a 3060-3069 port pool.

```
services/canvas-engine/src/
├── server.ts                          Express entry · POST /clone · POST /edit · SSE
├── pipeline/
│   ├── url-to-clone.ts                Phase 3 orchestrator (~487 LOC)
│   ├── edit-loop.ts                   Deterministic transforms (~332 LOC)
│   ├── sitepull-resolver.ts           Host-exact anatomy.json discovery (file you saw)
│   └── session-store.ts               In-memory Map<sessionId, CloneSessionState>
├── sandbox/
│   └── vite-pool.ts                   Port alloc · mkdtemp · Vite spawn (~277 LOC)
├── adapter/
│   ├── v1-schema.ts                   Zod schema for AnatomyV1
│   ├── v1-to-prompt.ts                Envelope → human-readable preamble
│   └── v1-to-edit-prompt.ts           Edit prompt formatter
├── pattern-library/
│   ├── index.ts                       23 patterns / 8 groups, picker with scoring
│   ├── normalize.ts                   Layer detection · TWO-WAY CONTRACT with extension
│   └── patterns/  (20 files)          Card · button · form · hero · list · modal · ...
├── vendor/lovable/
│   ├── VENDOR_SHA.ts                  firecrawl/open-lovable@69bd93b · MIT
│   ├── parse-blocks.ts                Vendored
│   ├── system-prompt.ts               Vendored
│   └── generate.ts                    STUB · returns hardcoded response · Phase 3b deferred
└── test/  (vitest + e2e .mjs)         Pattern-library coverage + 1 real-capture E2E
```

**Hot path** · `POST /clone` → `runUrlToClone` → SitepullResolver → zod parse → pattern picker → `buildRegionComponentSpecs` → `renderApp` → `vitePool.allocate` → SSE stream of `file` events.
**Edit path** · `POST /edit` → `runEdit` → intent regex → `applyTintEdit` / `applyRenameEdit` / `applyHideEdit` / `applyNoteEdit` → file write → HMR.

### 1c · `tools/anatomy-rewrite` + `tools/anatomy-research`

These do not run. They feed the runtime path indirectly.

| Dir | What it is | Status |
|---|---|---|
| `anatomy-rewrite/SPEC/` | 3 clean-room specs (adopted stylesheets · shadow DOM · canvas pre-capture). 63-73 lines each, behavior-only, no impl reference. | REFERENCE · waiting for Codex sessions to derive impls |
| `anatomy-rewrite/CODEX-PROTOCOL.md` | IP firewall · bans Codex from reading SingleFile / dom-to-image / html2canvas during impl | REFERENCE · governance doc |
| `anatomy-rewrite/DIFF-HARNESS.md` | SSIM ≥ 0.92 gate · pixel occlusion · canvas count match | REFERENCE · no `harness/reports/` exists yet |
| `anatomy-rewrite/TEST-CORPUS.md` | 50 URLs · 4 tiers (minimums · SPA tooling · auth dashboards · WebGL) | REFERENCE |
| `anatomy-research/AUDIT_FINDINGS.md` | 43 KB · locked 2026-04-22 · finding from 4 vendored repos | REFERENCE · `LOCKED` in body |
| `anatomy-research/{browser-use, JSON-Alexander, json-render, firecrawl, firecrawl-mcp-server}` | Vendored reference clones | REFERENCE archive · 170 MB total |
| `anatomy-research/plan-d-signal/` | Probe outputs · cold-fetch vs extension-mode benchmarks | REFERENCE |
| `anatomy-research/vendor-singlefile/` | 19 MB SingleFile source | REFERENCE · explicitly off-limits to Codex per protocol |

Plan D Specs 01-03 already shipped into `tools/anatomy-extension/lib/` (the lib files cited in 1a). The SPEC docs themselves are now historical — they describe what was built.

### 1d · End-to-end data flow

```
chrome tab
  └─► page-world.js (patches fetch/XHR)
         └─► CustomEvent: anatomy:request {ids, method, url, ts}
                └─► content.js (subscribes)
                       │
user Alt+click ────────┤
or auto-label dwell    │
                       ▼
                   regions[] (cascade r2-r12 + occlusion + dedup)
                       │
                       ▼
              chrome.storage.local  (key: hostname+pathname)
                       │
              ┌────────┴────────┐
              ▼                 ▼
     popup "export"     POST localhost:8088/ingest  (daemon, dev only)
              │                 │
              ▼                 ▼
        anatomy.json file  ◄────┘  written to web-audit root: .canvas/ or .tmp/ or audits/
                       │
                       ▼  (out-of-band file discovery)
              services/canvas-engine
                       │
                       ▼
              SitepullResolver.resolve(url)
                       │  (host-exact match against metadata.target)
                       ▼
              anatomyV1Schema.parse(envelope)
                       │
                       ▼
              pattern-library.pickPattern(region) × N
                       │
                       ▼
              renderApp(specs) → App.jsx + components/*.jsx
                       │
                       ▼
              vitePool.allocate(sessionId) → port 3060-3069
                       │
                       ▼
              SSE stream → live editable React in iframe
```

**Critical observation** · the seam between extension and canvas-engine is a **file on disk**, not an HTTP call. The extension writes `anatomy.json` somewhere; canvas-engine globs across `.canvas/`, `.tmp/`, `audits/` looking for anatomy.json files whose `metadata.target` host matches the requested URL. There is no daemon-mediated handoff. There is no event bus. There is no "the extension just finished, kick off canvas-engine" wire. This is loose coupling by design but it means the pipeline only works when the human runs both halves in sequence.

---

## 2 · Current capabilities (what works end-to-end)

### 2a · Extension

| Capability | State |
|---|---|
| Manual Alt+click labeling with HUD | WORKS · labels persist in chrome.storage.local |
| Auto-label cascade (r2-r12) + occlusion check | WORKS · 13 detection rules · pixel-sample occlusion |
| Pattern detection (>5 siblings, >60% dominance → "list") | WORKS · adaptive collapse (≤9 keep all · 10-30 keep 5 · >30 keep 2) |
| Dwell-based watching · 450-2600ms stillness | WORKS · 3s watch window |
| Text-density scoring · `fontSize² × WCAG-contrast` tiebreaker | WORKS · 93% calibration score |
| Shadow DOM (open) recursion | WORKS · WeakSet dedup |
| Canvas pre-capture (data-URL inline) | WORKS · 10 MB cap, taint-aware |
| Network interception via page-world | WORKS · fires `anatomy:request` events |
| **Chains[] populated in export** | **DOES NOT WORK** · interception fires but `chains[]` is always empty in the envelope |
| Cross-origin iframes | NOT SUPPORTED · only frame boundary labelable |
| SPA re-trigger on in-page navigation | NOT SUPPORTED |
| Daemon ingest target | hardcoded `localhost:8088` |
| Closed vocab gate | WORKS · `validateRegion()` enforces 11+ allowed strings |

### 2b · Canvas-engine

| Endpoint | State | Notes |
|---|---|---|
| `POST /clone` | WORKS | URL → SSE stream of file events → sessionId |
| `POST /edit` | WORKS for tint / rename / hide / note | Regex-based transforms · h2-rename brittle on nested elements |
| `GET /sessions` | WORKS | |
| `GET /sessions/:id/edits` | WORKS | History persisted in session-store |
| `DELETE /sessions/:id` | WORKS | Stops Vite, removes mkdtemp dir |
| `GET /health` | WORKS | Returns vendored open-lovable SHA |
| `runEdit` LLM-driven cross-file edits | NOT IMPLEMENTED | `@anthropic-ai/sdk` imported but never instantiated · Phase 3b stub |
| Asset vendoring (images / fonts / CSS) | **NOT IMPLEMENTED** | Generated components reference remote URLs that may 404 |

End-to-end has been verified once on HN: 80 regions → 82 files → live styled React clone in <2s · 3 ground-truth edits applied · visually correct. Memory log entry corroborates.

### 2c · Sample envelope (real, not synthesized)

A `services/canvas-engine/test/fixtures/anatomy-v1-realistic.json` exists. Sketch of its shape (typical for the real captures Bruke has on disk for hn-v1, example-v1, ycombinator, linear, figma, apify, gmail):

```json
{
  "version": "anatomy-v1",
  "metadata": {
    "target": "https://news.ycombinator.com/",
    "mode": "extension",
    "timestamp": "2026-04-26T...",
    "tools": ["anatomy-extension@0.4.4"]
  },
  "regions": [
    {
      "id": "header-nav",
      "n": 1,
      "name": "Header",
      "layer": "ui",
      "selector": "table.hnmain > tbody > tr:nth-of-type(1)",
      "bounds": { "x": 0, "y": 0, "w": 1280, "h": 36 },
      "detection": "sem-h1",
      "kind": "sem",
      "fetches": []
    }
  ],
  "chains": [],
  "layers": {
    "ui":  { "color": "#3b82f6" },
    "api": { "color": "#a855f7" },
    "ext": { "color": "#22c55e" },
    "lib": { "color": "#eab308" },
    "state": { "color": "#ef4444" }
  }
}
```

The `fetches[]` and `chains[]` fields are spec'd but rarely populated in real captures (network interception works in page-world.js, but the wire to write captured requests into the envelope on export has not been built).

---

## 3 · Component schema · current vs target

### 3a · What the pipeline emits today (AnatomyV1)

Closed at the contract: `contracts/schemas/AnatomyV1.v1.json` (committed `608d82c`, draft-07, ajv-validated against 7/7 real captures).

Region shape:

```
Region {
  id, n, name, layer (ui|api|ext|lib|state),
  selector (CSS), bounds {x,y,w,h},
  detection (open string · 11+ values · gated by validateRegion),
  kind (sem|click|list|card|custom|watch),
  note?, fetches[]?
}
```

Vocabulary is closed (`detection-vocab.js` mirrors `pattern-library/normalize.ts`). 11+ canonical detection strings: `r2`, `r4-button`, `r8-event-handler-attrs`, `manual`, `sem-h1`, `sem-h2`, `sem-h3`, `form`, `list`, plus a few r-rule variants.

### 3b · Target schema (your handoff prompt, for diffing only)

```
Component {
  id, type, purpose,
  content { headline, subheadline, cta_text, ... },
  position { order, viewport },
  signals [ "has_video", "has_social_proof_badge", "has_price", ... ]
}
```

### 3c · Diff matrix · current vs target

| Field family | Current AnatomyV1 | Target | Gap |
|---|---|---|---|
| Identity | `id` (slug), `n` (order) | `id` | Match. AnatomyV1 already carries order via `n`. |
| **Type** | `kind` (6 values: sem · click · list · card · custom · watch) | `type` (`hero`, `pricing`, `cta`, ...) | **WIDE.** Today's `kind` is structural ("it's a list"). Target's `type` is conversion-functional ("it's the hero"). Different ontology. |
| **Purpose** | none | `purpose` (`capture_attention`, `reduce_friction`, ...) | MISSING. Not a renamable field — needs an inference layer. |
| Architectural layer | `layer` (ui · api · ext · lib · state) | none | Current has more layers than target needs. Target ignores backend layers; today's layers are page-internal classification. |
| **Content** | partial · `name`, `note` only · raw text not extracted per-field | `content { headline, subheadline, cta_text }` | **WIDE.** No structured copy extraction today. |
| Position | `bounds {x,y,w,h}`, `n` ordering | `position { order, viewport }` | Easy fold. `viewport: above_fold` derivable from `bounds.y < scrollY`. |
| **Signals** | none | `signals[]` (`has_video`, `has_price`, `has_social_proof_badge`) | **MISSING.** The conversion-pattern feature vector. Doesn't exist today in any form. |
| Page-level | `metadata.target`, `metadata.mode`, `tools[]` | `page_type`, `category` | MISSING. No page classification or vertical/category tagging. |
| Performance / trust / friction meta | none | `meta.performance`, `meta.trust_signals`, `meta.friction_points` | MISSING. |
| Network | `chains[]` (spec'd, empty in practice) | none | Current has more than target needs — but it's empty anyway. |

**Net read** · the current schema is structural/architectural ("here is the DOM, here are its layers"). The target is conversion-semantic ("here is a hero with these signals selling this purpose"). They're not on the same axis. Going from one to the other is a **labeling problem**, not a refactor. Mapping `kind=list` to `type=pricing_table` requires either an LLM, a category-aware heuristic library, or a labeling vocabulary you bolt on top of the existing envelope.

The good news · AnatomyV1 doesn't block any of this. You can extend it by adding optional `purpose`, `content`, `signals`, `page_type`, `category` fields without breaking existing 7/7 real captures or the canvas-engine adapter.

### 3d · Where the contract lives

Single-source-of-truth · `contracts/schemas/AnatomyV1.v1.json`. Validator · `services/delta-kernel/src/tools/validate-anatomy-v1.ts` (ajv 8.x). Zod twin · `services/canvas-engine/src/adapter/v1-schema.ts`. No v0/v2 fragments. No competing schemas. This is a clean contract surface — protect it.

---

## 4 · Dependencies

### 4a · Extension

| Dimension | Reality |
|---|---|
| Runtime deps | **ZERO npm packages.** Pure vanilla JS. No bundler. |
| Vendored libs | None in production path. All `lib/*.js` is hand-written. |
| External APIs | `localhost:8088/dev/version` (hot-reload poll) and `/ingest` (daemon). **Hardcoded in source.** |
| Manifest permissions | `<all_urls>`, `storage`, `activeTab`, `scripting`, `tabs`, `alarms` |
| Telemetry / analytics | None observed. Does not phone home. Nothing leaves the machine except to localhost:8088. |
| Headless browser | None — runs in the user's actual Chrome. |
| Paid APIs | None. |
| ML models | None. Heuristic cascade only. |

### 4b · Canvas-engine

| Package | Used? | Notes |
|---|---|---|
| `express` 5.2 | YES | HTTP + SSE |
| `vite` 5.4 | YES | Sandbox dev servers |
| `react` 18.3 + `react-dom` | YES | Generated components |
| `tailwindcss` 3.4 + `postcss` + `autoprefixer` | YES | Vite pipeline |
| `zod` 3.23 | YES | AnatomyV1 input validation |
| `@anthropic-ai/sdk` 0.40 | **NO — imported, never instantiated** | Phase 3b deferred. ~10 MB unused. |
| `tsx` (dev) | YES | Hot-reload watch |
| `vitest` (dev) | YES | Unit tests |
| `ajv` (dev) | YES | Schema validation tooling |

Vendored code at `src/vendor/lovable/` (firecrawl/open-lovable@69bd93b, MIT). Three files vendored: `parse-blocks.ts`, `system-prompt.ts`, `generate.ts`. Of those, only the type/schema bits are actually exercised — `generate.ts` is a stub.

### 4c · anatomy-research vendored repos

170 MB on disk, all reference clones (`browser-use`, `JSON-Alexander`, `json-render`, `firecrawl`, `firecrawl-mcp-server`, `vendor-singlefile`). All MIT/Apache-licensed. Not on the runtime path. Bruke's CODEX-PROTOCOL.md explicitly fences them off from impl reading to keep the clean-room boundary.

---

## 5 · Gaps and risks

| # | Area | Component | Issue | Severity | Notes |
|---|---|---|---|---|---|
| 1 | Asset hoarding | extension | None detected. Canvas pre-captures inline as data-URLs, capped at 10 MB. Nothing written to disk by the extension itself. | OK | Legal posture clean here. |
| 2 | **Asset hoarding** | canvas-engine | **Generated components reference REMOTE asset URLs.** No vendoring. So you're not hoarding assets either, but the clone can break (404) or leak the user's IP to the source server when the iframe loads. | MEDIUM | Either vendor (re-introduces hoarding question) or proxy (better). Either way, decide. |
| 3 | Selector fragility | extension | `:nth-of-type` selectors break on SPA re-render. Labels don't survive. | HIGH | Try `data-testid` first; fall back to fuzzy structural match. |
| 4 | Hardcoded daemon URL | extension | `localhost:8088` baked into source. Not deployable to end users. | HIGH | Move to chrome.storage.sync, popup-configurable. |
| 5 | Empty `chains[]` | extension | Network interception works in page-world but the wire from `anatomy:request` events into the exported envelope's `chains[]` field is missing. Schema permits it; runtime never fills it. | MEDIUM | Half the conversion logic (which fetch fires when CTA clicked?) lives in chains. |
| 6 | Cross-origin iframes | extension | Most modern SaaS pages have embedded cross-origin frames you can't reach. Slack, Figma, Stripe checkouts. | MEDIUM | postMessage bridge into iframe, frame-aware selectors. |
| 7 | SPA re-trigger | extension | History API navigations don't re-run the labeling cascade. | MEDIUM | MutationObserver on `<body>` or hook history.pushState. |
| 8 | Session TTL | canvas-engine | Sessions accumulate forever in memory and on disk (mkdtemp). Only LRU eviction at capacity 10. Long-lived process leaks. | HIGH | `expiresAt` field + 5-min sweeper. |
| 9 | Vite port race | canvas-engine | Concurrent `allocate()` at capacity 10 can double-evict same session and collide on port binding. | HIGH | Serialize via `pLimit(1)` on allocate. |
| 10 | Iframe isolation | canvas-engine | Generated components render anatomy region HTML/CSS verbatim. No CSP, no sandbox attribute on the preview iframe. Malicious CSS or `data:` URLs from the scraped site could exfiltrate. | MEDIUM | Add `sandbox="allow-scripts"` (no `allow-same-origin`) on the preview iframe; CSP on Vite sandbox. |
| 11 | Anthropic SDK weight | canvas-engine | ~10 MB dep imported but never used. | LOW | Either delete until Phase 3b or lazy-`import()`. |
| 12 | Loose coupling between extension and canvas-engine | pipeline | The handoff is "user runs both halves in order, anatomy.json shows up on disk somewhere, canvas-engine globs to find it." No event, no callback, no daemon broker. | MEDIUM | Intentional today, but won't scale past one user. |
| 13 | Extension is mostly **untracked in git** | extension | 50+ files (manifest, popup, page-world, lib/*) sit untracked in main repo. Only `content.js` is tracked-and-modified. One reflash = everything gone. | **HIGH** | Single bulk commit. Memory entry is correct. |
| 14 | anatomy-research is 170 MB on the working tree | research | Vendored clones bloat clones/checkouts. Codex sessions are explicitly forbidden to read most of it anyway. | LOW | Move to `.archive/` or LFS pointer. AUDIT_FINDINGS.md stays in `docs/`. |
| 15 | Hardcoded test corpus = competitor URLs | rewrite | TEST-CORPUS.md lists 50 URLs (Linear, Notion, Excalidraw, Anthropic, Figma, Vercel, Stripe...). This isn't scope creep — it's the SSIM gate corpus. But it does mean those domains are live in your repo. | LOW · note | Worth knowing if/when you publish the repo. |
| 16 | Privacy / phone-home | extension | None observed. Local-only storage and fetch to localhost. | OK | |
| 17 | No production logging | canvas-engine | No pino/winston/console-wrapper. Server crashes leave no breadcrumbs beyond SSE error events the client may have already disconnected from. | MEDIUM | Add structured logger before deploy. |
| 18 | `applyRenameEdit` regex assumes `<h2>Old</h2>` | canvas-engine | Nested elements / styled spans / non-h2 → silent fail. | LOW-MEDIUM | AST-based edit when LLM lands. |
| 19 | Pattern-detection labeling is structural, not conversion-semantic | extension + canvas-engine | Today: `kind=list`. Target: `type=pricing_table`. The whole "purpose / signals / page_type / category" axis is missing. | **HIGH for the wedge** | This is the heart of the conversion-intelligence ask. See section 3c. |
| 20 | Idempotency | extension | Re-running on same URL produces near-identical envelope. Selectors stable for static pages, fragile for SPAs (see #3). | OK with caveat | Selector fix (#3) reinforces this. |

---

## 6 · Code quality flags

### Honest reads

**content.js (~2,700 LOC, single file).** Past the comfort zone. Well-organized internally — state, cascade, occlusion, dwell, HUD, export are all clearly demarcated — but adding chains[] (#5) or iframe support (#6) will push it over 3,500 and any further work becomes risky. **Split into `state.js` / `labeling.js` / `hud.js` / `export.js` / `index.js` is overdue.**

**Detection vocab is a contract, not a duplicate.** Both `tools/anatomy-extension/lib/detection-vocab.js` and `services/canvas-engine/src/pattern-library/normalize.ts` carry the same `normalizeDetection()` logic. Comments in both files explicitly call out the two-way contract. This is fine but you have **no test that fails if the two drift**. Worth a single CI step that diffs the two vocab tables.

**Vibe-code check.** No vibe-coded files found in the runtime path. anatomy-rewrite/ is genuinely small and purposeful (5 docs, no half-built code). anatomy-research/ is structured (vendored repos + probes + findings). The only "is this real?" file is `services/canvas-engine/src/vendor/lovable/generate.ts` which is explicitly a stub — fine, just don't ship it as if it were live.

**Dead code in canvas-engine.**
- `@anthropic-ai/sdk` imported and never instantiated.
- `buildSystemPrompt()` called but result discarded in `generate.ts`.
- `_dropCounters` populated but never read in extension cascade (debug artifact per memory).
- `rulesVersion` legacy migration code in extension (v2 hardcoded, migration path dead).

**Test coverage.**
- canvas-engine · pattern-library covered (72/72 vitest pass per memory). SitepullResolver, SessionStore, VitePool, EditLoop intent parsing — **no tests**.
- extension · no unit tests. One headless calibration harness for the text-grid (93% score). One smoke build selector. Python verifiers for vocab integrity (`dev-tools/verify_vocab.py`).
- E2E · `services/canvas-engine/test/e2e-real-capture.mjs` and `trainer-vs-truth.mjs` exist. Run on real captures.

**Comments.** Reasonable. Pattern picker scoring could use a block comment. Cascade rules r2-r12 are well-documented in source.

**Files >800 LOC.** Only `content.js`. `url-to-clone.ts` (487) and `vite-pool.ts` (277) are within range.

---

## 7 · What I'd do next, in priority order

These are cross-component, ordered by impact-on-the-wedge × likelihood-to-block-something-soon. Not all are large.

| # | Action | Component | Severity | Effort | Why |
|---|---|---|---|---|---|
| 1 | **Commit the untracked anatomy-extension files.** Single bulk commit. 50+ files. | extension | **CRITICAL** | 10 min | One reflash = the whole product gone. This is risk #13. Do this before anything else this session. |
| 2 | **Decide the "purpose / signals / page_type / category" labeling layer.** This is the wedge. AnatomyV1 is structural; the conversion-intelligence ask is semantic. Three options: (a) LLM pass at envelope-export time in the extension, (b) LLM pass in canvas-engine after parse, (c) a hand-curated heuristic vocab library. Pick one and prototype on hn-v1 + ycombinator + figma fixtures. | both | **HIGH** | 4-8 hr prototype | Without this layer, every component-level conversion datum is just "list" or "click" — no compounding. |
| 3 | **Wire `chains[]` from page-world.js into the export envelope.** Network interception fires today; the bridge to the exported anatomy.json is missing. | extension | HIGH | 3-4 hr | Half the conversion logic (which fetch corresponds to which CTA) is in there. Schema already permits it. |
| 4 | **Asset story for canvas-engine clones.** Either vendor (proxy through a local cache) or rewrite remote URLs to a 404-safe placeholder. Today the iframe leaks the user's IP to scraped sites and the clone breaks when assets 404. | canvas-engine | HIGH | 6-8 hr | Decide-before-you-ship. Vendoring is the question Bruke flagged in the prompt. |
| 5 | **Session TTL + Vite port serialization.** `expiresAt` + 5-min sweeper + `pLimit(1)` on `vitePool.allocate`. | canvas-engine | HIGH | 3-4 hr | Two unrelated bugs, similar fix surface. Without TTL the dev server leaks; without serialization parallel /clone calls collide. |
| 6 | **Make `localhost:8088` configurable.** chrome.storage.sync + popup field. Default still localhost. | extension | HIGH | 2-3 hr | Production-readiness blocker. Currently undeployable. |
| 7 | **Selector resilience for SPAs.** `data-testid` first → semantic role → fuzzy structural → `:nth-of-type` last. Stale-selector warning in HUD. | extension | HIGH | 5-7 hr | Today's labels die on the next React re-render. Major UX cliff for the targets that actually matter (pricing pages on SPAs). |
| 8 | **Split `content.js`.** Extract state / labeling / hud / export. No logic changes. | extension | MEDIUM | 2-3 hr | Unblocks #3, #6, and the SPA work in #7. Currently doing all four in one 2,700-line file is going to introduce bugs. |
| 9 | **Cross-origin iframe support.** postMessage bridge, frame-aware selectors. | extension | MEDIUM | 4-6 hr | Required to ever audit Slack / Figma / Stripe checkouts. |
| 10 | **Tests for SitepullResolver, SessionStore, VitePool, EditLoop intent parsing.** | canvas-engine | MEDIUM | 4-6 hr | These are the production code paths with zero unit coverage. |
| 11 | **CI step that diffs the two detection vocabs.** Fail the build if `lib/detection-vocab.js` and `pattern-library/normalize.ts` drift. | both | LOW | 1 hr | Cheap insurance for a contractual coupling that's load-bearing. |
| 12 | **Archive `anatomy-research/` to `.archive/`.** Keep `AUDIT_FINDINGS.md` in `docs/`. | research | LOW | 30 min | 170 MB out of working tree. |
| 13 | **Iframe sandbox + CSP on canvas-engine preview.** | canvas-engine | MEDIUM | 2 hr | Defense-in-depth. Render `sandbox="allow-scripts"` (no same-origin). |
| 14 | **Lazy-`import()` or delete the Anthropic SDK import** until Phase 3b. | canvas-engine | LOW | 15 min | Cosmetic but cheap. |

**My top three if you only do three this week** · #1 (commit), #2 (decide the conversion-semantic labeling layer), #3 (wire chains[]). Everything else is hardening; those three are the wedge.

---

## Appendix · what the audit did NOT cover

- No live URLs were scraped. No anatomy capture was generated during this audit.
- The extension was not loaded into Chrome and exercised. `dev-tools/verify_vocab.py` was not run.
- Canvas-engine was not booted; SSE endpoints were not hit; no Vite sandbox was allocated.
- The `services/delta-kernel/` validator was not run against real captures.
- `tools/codex-partner/` triple-review JSONs (committed in `2a1a3b3`) were not re-read; the audit assumed those findings overlap and stand on their own.
- Memory file claims (e.g., "72/72 canvas-engine tests pass") were taken on faith; they were not re-executed.

If you want me to run any of those next, say which.

---

## Deliverable handoff

This file IS the audit report. On approval, I'll save a copy into the worktree as `SCRAPER_PIPELINE_AUDIT.md` (alongside the other top-level audit docs like `BACKEND_AUDIT.md`, `FRONTEND_AUDIT.md`) so it's reviewable on the branch and squashable into the commit history if you want it in main.
