# Spec Drift Audit · 2026-05-11

## Summary

**YELLOW** — 4 drift items found across the three docs. Two BLOCK-level issues: `tools/anatomy-research/` is completely absent from disk despite a detailed section in PRE_ATLAS_MAP.md; and the `.passthrough()` claim about the Zod twin persists in canvas-engine README and contracts README body text, contradicting the actual strict `z.object()` code and the 2026-04-27 correction note.

---

## Drift Found

| File | Claim | Actual | Severity |
|---|---|---|---|
| `PRE_ATLAS_MAP.md` | `tools/anatomy-research/` exists at that path with vendored repos (`browser-use/`, `firecrawl/`, `json-render/`, etc.) | Directory does not exist. `tools/` contains only `anatomy-extension/`, `anatomy-rewrite/`, `codex-partner/` | **BLOCK** |
| `services/canvas-engine/README.md` (lines 65, 84) and `contracts/README.md` (Overview § line 19) | Zod twin `v1-schema.ts` uses `.passthrough()` on root/regions/chains/chainNodes/metadata | Actual code has zero `.passthrough()` calls. All schemas are strict `z.object()`; only `layersTaxonomySchema` uses `.catchall()`. The 2026-04-27 update note in PRE_ATLAS_MAP.md corrected this in the footnote, but the body text in canvas-engine README and contracts README Overview was never updated. | **BLOCK** |
| `PRE_ATLAS_MAP.md` (directory listing, `specs/` section) | Lists 19 spec files in `services/delta-kernel/specs/` (all `module-*`, `v0-*`, `ultra-low-streaming-sdk.md`, `phase-5b-*`, `phase-6a-*`) | 20 files on disk — `atlas-goals-api.md` exists but is absent from the listing. The stated count of "20 specification documents" is correct; only the listing is incomplete. | **WARN** |
| `PRE_ATLAS_MAP.md` (Mosaic Platform Services table, Inter-Project Dependencies diagram) | `code-converter` on port 3007 listed alongside `services/`-resident services with no explicit path | `services/code-converter/` does not exist. Service lives at `apps/code-converter/` (confirmed: `converter.py`, `server.py`, `patterns.json` present there). No explicit path stated in the port table, but the `services/` grouping context implies that location. | **WARN** |

---

## Verified Clean

- **Schema count:** 47 total in `contracts/schemas/` ✓ — 45 versioned `.v1.json` + 2 legacy unversioned (`CognitiveMetricsComputed.json`, `DirectiveProposed.json`) ✓
- **Spec count:** 20 `.md` files in `services/delta-kernel/specs/` ✓ (count is accurate, listing gap noted above)
- **Vendor SHA:** `VENDOR_SHA.ts` records `69bd93bae7a9c97ef989eb70aabe6797fb3dac89` — short form `69bd93b` in all three docs matches ✓
- **content.js commit SHA:** `git log --oneline tools/anatomy-extension/content.js | head -1` → `28caebf fix(anatomy-extension): buildSelector emits tag#id…` ✓
- **File existence (all present):**
  - `services/canvas-engine/src/adapter/v1-schema.ts` ✓
  - `services/canvas-engine/src/vendor/lovable/parse-blocks.ts` ✓
  - `services/canvas-engine/src/vendor/lovable/system-prompt.ts` ✓
  - `contracts/validate.py` ✓
  - `contracts/schemas/AnatomyV1.v1.json` ✓
  - `tools/anatomy-extension/ANATOMY_V1_SCHEMA.md` ✓
  - `tools/anatomy-extension/content.js` ✓
- **Port table / service directories:** All checked ports map to existing service directories — delta-kernel (:3001), aegis-fabric (:3002), mosaic-orchestrator (:3005), cortex (:3009), optogon (:3010), canvas-engine (:3050) ✓
- **canvas-engine port defaults:** `src/server.ts` defaults to `PORT=3050`, Vite pool `[3060, 3069]` ✓
- **Vitest test count:** 84 `it()` calls across 5 `.test.ts` files (adapter: 11, util: 11, pattern-library: 39, edit-loop: 13, composition: 10) ✓ matches "84 vitest pass"
- **`npm run validate:anatomy`:** NOW WIRED in `services/delta-kernel/package.json` → `tsx src/tools/validate-anatomy-v1.ts`, and the file exists on disk. This was reported MISSING on 2026-04-27; it has been added since that audit. ✓
- **Portless services:** `services/ws-gateway/`, `services/crucix/`, `services/perception/`, `services/triangulation/` all confirmed present ✓

---

## Notes

1. **`validate:anatomy` drift resolved:** The 2026-04-27 manual audit flagged `npm run validate:anatomy` and `services/delta-kernel/src/tools/validate-anatomy-v1.ts` as missing. Both are now present and wired. No action needed.

2. **Internal contradiction in PRE_ATLAS_MAP.md:** The 2026-04-27 update footnote reads *"AnatomyV1 Zod twin re-described as STRICT z.object (NOT `.passthrough()` as earlier text claimed)"* — but the body text of section 7 (canvas-engine) and the Inter-Project Dependencies section were **not** edited to match. The footnote says it was fixed; the body says it wasn't. Same split in `contracts/README.md` where the Overview says `.passthrough()` and the Mosaic Platform Services section says STRICT. All three docs need their body text aligned with the code.

3. **`atlas-goals-api.md` is undocumented work:** The file exists at `services/delta-kernel/specs/atlas-goals-api.md` with no mention anywhere in the three audited docs except the count of 20. Worth adding to the PRE_ATLAS_MAP.md directory listing.

4. **`tools/anatomy-research/` likely deleted:** Given the status note "Reference material — never edit vendored upstream code", this directory was likely deleted at some point after the doc was written (possibly as a cleanup of large vendored repos). The doc section should be removed or updated to reflect its absence.
