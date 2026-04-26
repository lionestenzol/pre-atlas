# canvas-engine

URL · anatomy · open-lovable · live editable React clone.

Replaces the `claude -p` edit loop wired into Canvas c3+c4 (`web-audit/lib/serve.js`) with an anatomy-driven open-lovable pipeline.

## Status

**Phase 1 of 6** · Foundation. Health endpoint + stub `/clone` that streams hardcoded `<file>` blocks.

See `~/.claude/plans/what-would-happen-if-robust-sedgewick.md` for the full plan.

## Quickstart

```bash
cd services/canvas-engine
npm install
npm run dev
# Server boots on port 3050
# (3010 is owned by Optogon · canvas-engine = 3050 · Vite pool = 3060-3069)

curl http://localhost:3050/health
# {"ok":true,"version":"0.1.0","phase":1}

curl -X POST http://localhost:3050/clone \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
# Streams SSE events with <file> blocks
```

## Architecture

```
Canvas surface
  │
  ▼  POST /clone | /edit
canvas-engine (port 3050)
  ├─ adapter/v1-to-prompt.ts        (Phase 2)
  ├─ vendor/lovable/                (vendored from open-lovable@<SHA>)
  │   ├─ generate.ts                (Phase 1: stub · Phase 3: real LLM)
  │   ├─ parse-blocks.ts            (Phase 1)
  │   ├─ system-prompt.ts           (Phase 1)
  │   └─ VENDOR_SHA.ts              (Phase 1)
  ├─ pipeline/
  │   ├─ url-to-clone.ts            (Phase 3)
  │   └─ edit-loop.ts               (Phase 4)
  └─ sandbox/
      └─ vite-pool.ts               (Phase 3)
```

## Phase verification

**Phase 1 (current):**
- [x] `npm run dev` boots on port 3050
- [x] `GET /health` returns `{ok: true, version: "0.1.0", phase: 1}`
- [x] `POST /clone` returns SSE stream with `<file>` blocks
- [x] `VENDOR_SHA` constant references actual commit

## Vendoring

Code in `src/vendor/lovable/` is ported from [firecrawl/open-lovable](https://github.com/firecrawl/open-lovable).

**Do not modify vendored files in place.** To upgrade:

1. Bump `VENDOR_SHA` in `src/vendor/lovable/VENDOR_SHA.ts`
2. Re-port the changed sections from upstream
3. Update tests · re-run Phase 1 verification

## Why local Vite, not E2B

- Free tier: local Vite pool (3011-3020). Bruke's Canvas runs locally; staying local keeps parity with c3+c4.
- Paid tier (Phase 7+): E2B cloud sandbox. Vendor surface is ready (see `sandbox/` interface). Cloud impl deferred.
