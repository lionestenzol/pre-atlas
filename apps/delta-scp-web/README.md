# delta-scp-web — Delta SCP front-end

A polished single-page UI for **Delta SCP**: paste a public repo URL → get a
token-cheap **symbolic skeleton** (file tree + top-level symbols) plus the
**graph-memory layer** (AST nodes + import edges) that is the product's
differentiator. Vite + React; no hand-rolled templating.

## Topology (two pieces, two repos)

```
 apps/delta-scp-web (this dir, Pre Atlas)         pre-atlas/services/delta-scp
 ┌──────────────────────────────┐  /api proxy   ┌────────────────────────────┐
 │ Vite + React UI  :5174        │ ───────────▶  │ demo-server.ts gateway :3012│
 │  · repo input + budget slider │   (vite.config│  · POST /jobs  → compress   │
 │  · skeleton tree + symbols    │    rewrites   │  · GET  /jobs/:id           │
 │  · graph-memory panel         │    /api → 3012)│  · reuses the REAL engine:  │
 │  · copy JSON / Markdown       │ ◀───────────  │    compressRepository +     │
 └──────────────────────────────┘   job result   │    buildGraphRows (unchanged)│
                                                  └────────────────────────────┘
```

The UI only speaks HTTP. The backend is the **existing Delta SCP compression
engine** — `src/demo-server.ts` is a thin, Supabase-free adapter that wraps
`compressRepository` (source.ts → compressor.ts) and `buildGraphRows` (graph.ts)
and returns the same `compressed_state` shape the production worker writes, plus
the AST graph the production HTTP gateway does not expose. It does **not** modify
or replace the real gateway (`server.ts`); run that once Supabase creds are set.

## Run it

**1. Backend adapter (the live :3012 service):**
```bash
cd C:/Users/bruke/pre-atlas/services/delta-scp
npx tsx src/demo-server.ts          # listens on :3012, no Supabase needed
# (optional) set SCP_API_KEY in the env to require a Bearer key
```

**2. Front-end:**
```bash
cd C:/Users/bruke/Pre Atlas/apps/delta-scp-web
npm install      # first time
npm run dev      # http://localhost:5174  (proxies /api → :3012)
```

Paste a Git URL (e.g. `https://github.com/sindresorhus/yocto-queue.git`) and hit
Compress, or click an example chip.

## Notes

- The UI polls `GET /jobs/:id` until the job is terminal, so it works unchanged
  against **either** the demo adapter (returns a complete job immediately) **or**
  the real Supabase-backed async queue (returns `pending`, then completes).
- Copy-to-clipboard uses the Clipboard API with an `execCommand` fallback
  (`src/lib/clipboard.js`).
- For the production async queue (real `server.ts` on :3012), fill the service
  `.env` with `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SCP_API_KEY`, run
  `npm run migrate`, then `npm start` — and point this UI at it unchanged.
