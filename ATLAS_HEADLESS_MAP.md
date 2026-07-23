# ATLAS_HEADLESS_MAP.md — the back end that survives the UI

> **Phase 1 / major structure.** The headless-survival partition: what runs with no UI,
> what the UI is actually a thin client over, what little you'd lose, and where the
> engine stalls today. Built first-hand from `atlas-manifest.yaml`, `audit/manifest-overlay.yaml`,
> `.claude/launch.json`, and a route/CLI sweep. Date: 2026-06-29.
>
> This is NOT a fifth inventory. It is keyed to one decision: **can I delete the UI without losing function?**
> Short answer: yes, with 3 verifies and 4 backend gates to flip.

---

## TL;DR — the finding

**Headless Atlas already exists.** It is `delta-kernel` (the hub, :3001) + its governance
daemon (9 cron jobs, */5 heartbeat, already active) + ~15 spoke service APIs + a real CLI layer
(`atlas.ts`, `atlas-ai.ts`, `atlas-cli`, `droplist/cli.py`, the sensor actor scripts).

The system's own spine loop is:

```
cognitive-sensor (analyze)  →  optogon/cortex (propose/execute)  →  droplist (packetize)  →  delta-kernel (commit)  →  lattice/inpact (project)
        DORMANT                       GATED (env-off)                   on-demand                ACTIVE daemon              ← THIS is the UI
```

Only the **last step (project) is the UI.** Steps 1-4 are all back end. So "go headless" does
not break the spine. It removes the projection layer. What is NOT running today is the *front*
(sensor dormant) and the *middle* (executors gated off) — and those are gates by design, not
UI coupling. Killing the UI changes none of that.

**What you lose by deleting the UI:** visualization and click-affordance (lattice's Cytoscape
graph, cycleboard's board view, inpact's daily-flow screens). **Not** capability — the
capability is API + CLI underneath every one of them.

---

## Bucket A — already headless (the back end; delete the UI, lose nothing)

Every row has a wire surface (HTTP API) and/or a CLI. These ARE the headless system.

| Service | Port | Entry | Headless control surface | Lifecycle |
|---|---|---|---|---|
| **delta-kernel** (HUB) | 3001 | `src/api/server.ts` | Full `/api/*` (state, cycleboard, tasks, goals, signals, timeline, work, law, life-signals, daily-brief) + **CLI `src/cli/atlas.ts`, `atlas-ai.ts`** + `GET /api/cli/manifest` + governance daemon | **active** |
| aegis-fabric | 3002 | `src/api/server.ts` | Full `/v1/*` (agents, approvals, policies, tenants, audit, metering, webhooks) | active |
| atlas-map-api | 3072 | `atlas_map_api.server` | `/map/*` (launch/stop/locate/search), `/describe`, `/call` gateway, `/items` + **MCP `atlas-map`** + **CLI `tools/atlas-cli`** | active |
| droplist | 3073 | `droplist.server` | `/api/*` (drop, dag, packets, brief) + **CLI `droplist/cli.py`** + `daemon.py` | on-demand |
| cortex | 3009 | `cortex.main` | `/inpact/run/{module}`, `/tasks/*`, `/status` | **gated** (env-off) |
| optogon | 3010 | `optogon.main` | `/session/*` (path-runtime), `/paths`, `/signals` | **gated** (env-off) |
| search-stack | 3070 | `search_stack.server` | `/search`, `/extract`, `/budget` + MCP `search_stack` | active |
| memory-hub | 3071 | `memory_hub.server` | `/save`, `/search`, `/entity/{}`, `/idea/{}` | active |
| uasc-executor | 3008 | `server.py` | `/exec`, `/commands`, `/runs` + `daemon.py` (HMAC) | active |
| cognitive-sensor | 8765 | `triage_server.py` | `/api/conv/*`, `/api/decide` + actor scripts `auto_triage.py`, `run_daily.py`, `auto_actor.py`, `fs_actor.py` | **dormant** |
| canvas-engine | 3050 | `src/server.ts` | `/clone`, `/edit`, `/sessions` | active |
| code-converter | 3007 | `server.py` | `/convert`, `/patterns` | active (⚠ RCE flag) |
| triangulation | 3075 | `triangulation.api` | `/verify`, `/library/*` | stub |
| ws-gateway | 3013 | `index.ts` | socket.io events (no REST) | dormant |
| **legacy/retired** | — | — | mosaic-orchestrator :3005, mosaic-dashboard :3000, openclaw :3004, mirofish, ai-exec-pipeline :5000, blueprint-generator :3030 | retired |

Cross-repo node: **delta-scp** :3012 (sibling repo `C:/Users/bruke/pre-atlas`) — `src/cli.ts` + demo-server.

---

## Bucket B — the UI surfaces (what dies) and their headless twin

Each static shell is a thin client. The "calls" column is hand-traced in `manifest-overlay.yaml` `surfaces:`.

| UI surface | Path / port | What it calls (its real logic, in the back end) | Headless replacement | You lose | Verdict |
|---|---|---|---|---|---|
| **inpact** | `apps/inpact` :3006 | delta-kernel `GET /api/cycleboard`, daily-brief/state/signals; cortex `POST /inpact/run/{module}` | delta-kernel API + cortex API + `atlas.ts` CLI | daily-flow / onboarding screens | **DROP** (verify cortex owns module logic) |
| **lattice** | `apps/lattice` :3011 | delta-kernel `GET /api/lattice/viewmodel`, **`POST /api/lattice/correct`** (load-bearing write-back), `/items` | viewmodel + correct are API endpoints | Cytoscape tree/graph/timeline **viz** | **DROP** (the correction loop is API, not UI) |
| **atlas-setup** | `atlas-setup.html` via :8888 | atlas-map-api `/map/launchables`, `/map/{start,stop,restart,halt}`; delta-kernel `/api/auth/token` | atlas-map-api `/map/*` + MCP + `atlas-cli` + `setup/apply.py` | clickable boot grid | **DROP** (fully replaced today) |
| **cycleboard** | `cognitive-sensor/cycleboard` :8889 | delta-kernel cycleboard blob (GET/PUT) | `atlas.ts` CLI ("CycleBoard parity") + `cycleboard/cli.ts` | board view | **VERIFY** parity, then drop (core surface — check hardest) |
| cortex-dashboard | `services/cortex` :8891 | cortex API | cortex `/status`, `/tasks/*` | viewer | DROP |
| aegis-landing/dashboard | `aegis-fabric` :8890 | aegis `/v1/*` | aegis API | viewer | DROP |
| hydra | `apps/hydra` :8898 + engine :8899 | hydra-engine → delta-scp | engine is the back end | game UI | DROP |
| delta-scp-web | `apps/delta-scp-web` :5174 | delta-scp :3012 | delta-scp `cli.ts` + API | SaaS UI | DROP |
| crucix | submodule | own express `/api/data` | semi-backend (server+UI in one) | dashboard | KEEP server / drop view |
| anatomy / thread-cards / tour-test / audit-map / c110-trace | various :889x | mostly static viewers/experiments | none needed | viz/experiments | DROP |

**No true orphan found at the structural level.** Every surface resolves to a back-end call or
a static experiment. The three to *prove* before cutting (below) are inpact module logic,
cycleboard CLI parity, and lattice correction loop — because those are the load-bearing ones.

---

## Where headless Atlas stalls today (the failure axis)

These are back-end conditions, independent of the UI. Going headless does not cause them; it
*exposes* them, because the UI was the only thing hand-cranking some of them.

1. **Front of spine is dark.** `cognitive-sensor` is **dormant** — the triage arm
   (`auto_triage → cortex_bridge → decisions_to_atlas`) is **UNSCHEDULED**, runs only when
   hand-cranked via `at`. With no UI and no scheduler, the analyze step never fires. → A headless
   Atlas must schedule `run_daily.py` / `auto_triage.py`.
2. **Middle of spine is gated off.** `cortex` executes only with `CORTEX_BRIDGE_APPLY=1` +
   `CORTEX_BRIDGE_RUN_PROPOSAL=1`. `optogon` writes back only with `AUTO_TRIAGE_APPLY=1`. All
   default off. → Decide: leave gated (safe) or flip for autonomy.
3. **Auth on writes.** delta-kernel needs Bearer key (`GET /api/auth/token`, exempt). atlas-map-api
   needs `X-Atlas-Token` (gitignored `.atlas-write-token`). uasc needs HMAC. → A headless driver
   must fetch/hold these.
4. **Port collisions that the UI was hiding — RESOLVED 2026-07-15.** ws-gateway :3011 == lattice
   :3011; c110-trace :8897 == audit-map :8897. Fixed directly (ws-gateway → 3013 + `WS_PORT` env
   override, c110-trace → 8901) via `register-preview-server.py`'s port-collision guard, ahead of
   any headless migration. Going headless would still drop the static servers as a category, but
   that's no longer needed to resolve this specific item.
5. **Data-inflation.** `cognitive-sensor` loc (~116k) is ~half multi-MB JSON dumps, not code. Treat
   it as a data store with a pipeline, not a 116k-line service to reason about.
6. **Submodule trap.** `services/crucix` is a git submodule, habitually `-dirty`. Never bulk
   `git add -A`. Commit inside it first.

---

## The headless driver already half-exists

You do not need to build a control plane. You need to pick one of these as the headless front door:

- **`tools/atlas-cli`** (Python) — drives atlas-map-api's `/map`, `/describe`, `/call`, `/items`.
- **`delta-kernel/src/cli/atlas-ai.ts`** — the JSON-native CLI for agents over the hub.
- **MCP `atlas-map`** (in-process) — same snapshot, callable from any Claude session.
- **atlas-map-api `/call` gateway** — proxy any surface's capability over one HTTP endpoint.
- **`tools/seam/run.py`** — the seam runner, content-addressed Receipts across the wired tools.

Known gap (from memory): the self-describing `/describe` + `/call` surfaces are **unused by the UI** —
which is exactly why they survive UI death intact. That gap becomes the headless feature.

---

## Verify-before-you-cut (the 3 load-bearing claims)

Do NOT delete a UI until these are proven against HEAD (each is one recon pass):

1. **inpact module logic lives in cortex, not inpact JS.** Check `apps/inpact/js/` for any compute
   that isn't a fetch to cortex/delta-kernel. If found → that's an orphan, build a CLI first.
2. **cycleboard CLI parity is real.** `atlas.ts` vs `cycleboard/js/*` — confirm every board mutation
   has a CLI/API path. (Memory claims parity; 4 days old, flagged stale.)
3. **lattice correction loop is fully server-side.** `POST /api/lattice/correct` must accept the
   same payload the Cytoscape UI builds — else the correction capability is trapped in the graph.

---

## Phase 2 / 3 (not this pass)

- **Phase 2:** for any orphan the verifies surface, spec the smallest CLI/API that frees it.
- **Phase 3:** the full 7-axis per-system dossier (does / components / how / purpose / indicates /
  contributes / stalls). Worth it after the partition, not before — it overlaps your existing
  `REPO_RUNDOWN.md` / `FORENSIC_DOSSIER` / `CLAUDE_INVENTORY`.
