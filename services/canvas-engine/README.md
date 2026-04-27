# canvas-engine

URL · anatomy · open-lovable · live editable React clone.

Replaces the `claude -p` edit loop that lived in `web-audit/lib/edit.js` (now deleted; `POST /edit` returns 410 Gone). `web-audit/lib/serve.js` `/canvas` route defaults to `engine=v2` and proxies SSE here.

## Status

**6 phases shipped 2026-04-26** · 84 vitest pass post trainer audit (2026-04-27) · PR #11 (2026-04-27) hardens the producer-consumer contracts.

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation (TS+Express scaffold) | ✓ shipped |
| 2 | Zod adapter for AnatomyV1 (`src/adapter/v1-schema.ts`) | ✓ shipped |
| 3 | URL → live-Vite-clone pipeline (in-process Vite pool 3060-3069) | ✓ shipped |
| 3b | Real Anthropic SDK swap-in for transforms | deferred |
| 4 | Edit loop (tint/rename/hide transforms, HMR write-through, conversation history) | ✓ shipped |
| 5 | web-audit migration proxy (`/canvas` → `engine=v2`) | ✓ shipped |
| 6 | `claude -p` edit loop deletion | ✓ shipped |
| 7+ | E2B paid sandbox tier | deferred |

End-to-end verified on HN capture: 80 regions → 82 files → live styled React in <2s · 3 ground-truth edits applied · visual confirmed.

See `~/.claude/plans/what-would-happen-if-robust-sedgewick.md` for the original plan and `~/.claude/projects/C--Users-bruke-Pre-Atlas/memory/project_canvas_engine.md` for the current state record.

## Quickstart

```bash
cd services/canvas-engine
npm install
npm run dev
# Server boots on port 3050
# (3010 is owned by Optogon · canvas-engine = 3050 · Vite pool = 3060-3069)

curl http://localhost:3050/health

# Clone a URL using the anatomy.json captured in ~/web-audit/.canvas/<host>/
curl -X POST http://localhost:3050/clone \
  -H "Content-Type: application/json" \
  -d '{"url":"https://news.ycombinator.com"}'
# Streams SSE events with <file> blocks → live React clone on a Vite port
```

Boot via `.claude/launch.json` `canvas-engine` entry for the integrated dev experience.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health probe |
| `/clone` | POST | URL + anatomy → live React clone session |
| `/edit` | POST | Edit transform via SSE (tint/rename/hide) |
| `/sessions` | GET | List active sessions |
| `/sessions/:id/edits` | GET | Edit history for a session |
| `/sessions/:id` | DELETE | Release Vite port back to pool |

## Architecture

```
Canvas surface (web-audit/lib/serve.js /canvas?engine=v2)
  │
  ▼  POST /clone | /edit  (SSE proxy)
canvas-engine (port 3050)
  ├─ adapter/
  │   ├─ v1-schema.ts             (zod twin · .passthrough() lockstep with JSON Schema)
  │   ├─ v1-to-prompt.ts          (anatomy → prompt)
  │   └─ v1-to-edit-prompt.ts     (anatomy + edit intent → prompt)
  ├─ pattern-library/             (region → component pattern picker)
  │   ├─ patterns/                (clickable-link, clickable-button, clickable-pill, …)
  │   ├─ normalize.ts             (TAG_OVERRIDES: input/textarea/select→form, ul/ol→list)
  │   └─ util.ts                  (leafTag, isAnchorSelector — leaf-only)
  ├─ vendor/lovable/              (vendored at firecrawl/open-lovable@69bd93b)
  │   ├─ parse-blocks.ts
  │   └─ system-prompt.ts
  ├─ pipeline/
  │   ├─ url-to-clone.ts
  │   └─ edit-loop.ts
  └─ sandbox/
      └─ vite-pool.ts             (in-process Vite pool 3060-3069 · onSessionReleased callback)
```

## Producer-consumer contract

Anatomy producer is the Chrome anatomy extension at `tools/anatomy-extension/`. The Zod twin in `src/adapter/v1-schema.ts` uses `.passthrough()` on root/regions/chains/chainNodes/metadata — **mandatory two-way contract** with `contracts/schemas/AnatomyV1.v1.json`. Adding a field to one without the other = silent drop. Same lockstep discipline applies to the closed detection vocabulary in `pattern-library/normalize.ts`.

Producer-side smoke at `tools/anatomy-extension/lib/_smoke-build-selector.mjs` locks the round-trip contract: `tag#id` selectors emitted by `content.js` must decode back to the right tag in canvas-engine's `leafTag()`.

## Pattern library trainer

Self-grading trainer at `test/trainer-vs-truth.mjs` uses leaf-tag truth from selector paths to audit the pattern picker. Three reports:

1. **GROUP-LEVEL ACCURACY** · rigorous, deterministic. 100% (532/532).
2. **STRICT PATTERN ACCURACY** · rigorous. 7 tags whose leaf uniquely determines a sub-pattern (header→landmark/header, h1→heading/hero, etc). 100% (27/27).
3. **HEURISTIC PATTERN REPORT** · explicitly labeled "NOT a truth metric." For stylistic-variant tags. 90.7% (458/505).

Six-round Codex audit progression: 84 → 87 → 89 → 91 → 92 → 90 → 97 APPROVE.

## Vendoring

Code in `src/vendor/lovable/` is ported from [firecrawl/open-lovable](https://github.com/firecrawl/open-lovable) at pinned commit `69bd93b`.

**Do not modify vendored files in place.** To upgrade:

1. Bump `VENDOR_SHA` in `src/vendor/lovable/VENDOR_SHA.ts`
2. Re-port the changed sections from upstream
3. Update tests · re-run vitest

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `WEB_AUDIT_ROOT` | `os.homedir()/web-audit` | Where to read `.canvas/<host>/anatomy.json` from. Set if your sitepull captures live elsewhere. |
| `ANATOMY_SCHEMA_PATH` | `contracts/schemas/AnatomyV1.v1.json` | Override for verify scripts. |
| `PORT` | `3050` | Service port. |

## Why local Vite, not E2B

- **Free tier:** in-process Vite pool 3060-3069. Bruke's Canvas runs locally; staying local keeps parity with the original c3+c4 stack.
- **Paid tier (Phase 7+):** E2B cloud sandbox. The `sandbox/` interface is ready for it; cloud implementation deferred.

## Related

- Plan: `~/.claude/plans/what-would-happen-if-robust-sedgewick.md`
- Memory: `~/.claude/projects/C--Users-bruke-Pre-Atlas/memory/project_canvas_engine.md`
- Memory: `~/.claude/projects/C--Users-bruke-Pre-Atlas/memory/project_canvas_trainer_audit.md`
- Producer: `tools/anatomy-extension/`
- Schema: `contracts/schemas/AnatomyV1.v1.json` + `tools/anatomy-extension/ANATOMY_V1_SCHEMA.md`
