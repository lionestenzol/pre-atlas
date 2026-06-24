# Retired-Services Autopsy — verified 2026-06-24

> **UPDATE 2026-06-24:** triangulation **REVIVED** — `api.py` now wraps the working
> `verify()` in 3 FastAPI endpoints on **port 3074**, registered in the
> self-description registry (lifecycle `live`, 4 caps) + `.claude/launch.json`.
> Booted live: `/healthz` ok, `/verify` returns real verdicts. 54/54 tests
> (46 + 8 new api). The remaining 7 stay dead; the cortex→mosaic question (below)
> is still open.

> Question (Bruke): *"were these retired because they were bad, or only because
> they had nothing to connect to?"* — i.e. would the capability registry / spine
> revive them. Method: 8-agent forensic workflow, then an independent code-recon +
> repo-inventory **verify pass** (rg/jq/tokei, two angles per claim). Counts are
> deterministic; absence/consumer claims cite the actual greps.

## Verdict summary

**0 clean REVIVE · 1 NEEDS-BUILD · 7 DEAD.** The hypothesis holds for exactly one
service (triangulation). The "Mosaic tier" wasn't orphaned — it was the *old
architecture* deliberately replaced by the delta-kernel hub + optogon + lattice.

| Surface | Why it died | Spine fixes it? | Verdict |
|---|---|:--:|---|
| **triangulation** | ORPHANED — core `verify()` works (46/46 tests cold-start), never got an HTTP face or a caller | ✅ yes | 🟢 **REVIVE** |
| mirofish | MISSING_DEP (Neo4j+Ollama never provisioned) + superseded by cognitive-sensor | ❌ | 💀 dead |
| mosaic-orchestrator | SUPERSEDED by optogon+delta-kernel (doctrine reversal); ran real traffic | ❌ | 💀 dead* |
| mosaic-dashboard | UI for the dead Mosaic backend tier; lattice replaced it | ❌ | 💀 dead |
| openclaw | needs the retired orchestrator upstream + bot tokens never set | ❌ | 💀 dead |
| ai-exec-pipeline | contract-less duplicate of cortex's Ghost Executor | ❌ | 💀 dead |
| blueprint-generator | zero-coupling static UI, superseded by canvas-engine | ❌ (never needed one) | 💀 dead |
| perception | INCOMPLETE — 9/13 modules are `NotImplementedError` | ❌ (unbuild, not unwire) | 💀 dead |

## Verify pass — what survived two angles

| Claim | Verdict | Evidence |
|---|:--:|---|
| mosaic-orchestrator = 42 routes | ✅ | `rg -o` route decorators = 42 |
| perception = 9/13 modules `NotImplementedError` | ✅ | 13 `.py`, 9 raise it |
| openclaw ≈ 918 LOC | ✅ | tokei = 918 Python |
| openclaw bot tokens blank | ✅ | `.env.example` TELEGRAM/SLACK/DISCORD empty |
| blueprint deps = next/react/react-dom only; 0 service_edges | ✅ | `jq` deps + `[]` |
| triangulation api = `NotImplementedError`×3; 46/46 tests pass | ✅ | api.py:11,15,19; pytest |
| mirofish — no **live** HTTP consumer | ✅ | `:3003` URL only in retired openclaw + mosaic-orch; memory-hub ref is an inert placeholder returning `[]` |
| perception / triangulation — no live importers | ✅ | only tests + catalog + the coverage test reference them |
| **mosaic-orchestrator "zero runtime consumers"** | ❌ **BUSTED** | cortex (LIVE, autostart) calls it — see below |
| mirofish code "copied into cognitive-sensor" | ❌ unconfirmed | no `*mirofish*` files in `services/cognitive-sensor` |

\* **mosaic-orchestrator's DEAD verdict is shaky.** A live service is wired to it:
- `services/cortex/src/cortex/config.py:13` → `MOSAIC_URL = "http://localhost:3005"`
- `services/cortex/src/cortex/agents/planner.py:120` → `POST {MOSAIC_URL}/api/v1/tasks/execute`
- `services/cortex/src/cortex/agents/planner.py:169` → `POST {MOSAIC_URL}/api/v1/compound/run`
- `services/cognitive-sensor/run_daily.py:35` → hardcodes `http://localhost:3005`

cortex is gated (`CORTEX_BRIDGE_APPLY=1`, default off) so this may be a dormant
path — but the wiring is real, which the autopsy flatly denied.

**RESOLVED 2026-06-24 — cortex→mosaic is dormant human-triggered dead code, not a
live dependency. mosaic-orchestrator's DEAD verdict HOLDS.** Evidence:
- Nothing in any backend creates `RUN_PIPELINE`/`COMPUTE_METRIC` intents — the only
  creators are buttons + a regex parser in cortex `dashboard.html:130,133,189-192`
  (`quickFire('run_pipeline','mosaic',…)`). `rg "RUN_PIPELINE|COMPUTE_METRIC"` over
  `src/` returns only the enum defs + `@template` decorators.
- cognitive-sensor `run_daily.py:167` POSTs `:3005/api/v1/workflows/daily`, but
  `run_daily` has no cron/launch entry; it runs only via the manual `atlas daily`
  CLI (`atlas_cli.py:17`), and `atlas_agent.py:91` *inlines* the steps rather than
  calling it.
- The cortex executor (`executor.py:157-165`) WOULD fire the HTTP call — so these
  are real, latent call sites, just never triggered autonomously.

**Cleanup (not revive):** to make those two manual features work, repoint them at
the live superseder (optogon / delta-kernel) or delete the dead call sites — do NOT
revive mosaic-orchestrator. Sites: cortex `dashboard.html:130,133` + `planner.py`
RUN_PIPELINE/COMPUTE_METRIC templates; cognitive-sensor `run_daily.py:35,167`.

## The one to revive: triangulation

Verification sidecar for the anatomy/DOM scraper (DOM + spatial + visual signals,
quorum-voted verdict). Logic is done and tested; it only ever lacked discovery +
a caller — exactly what the registry now provides. Smallest revive:
1. Wrap working `verify()` in 3 FastAPI endpoints (Phase C is glue, not new logic)
2. Port **3074** (NOT 3010 — collides with optogon)
3. Register its `verify` capability in the registry → discoverable
4. Point one anatomy-extension caller at it

## Salvage from the dead (harvest parts, don't revive shells)
- mosaic-orchestrator → `compound_loops/` + `metering/` could port onto optogon
- mosaic-dashboard → `src/lib/proxy.ts` + typed Socket.IO hooks into lattice
