# Atlas Consolidation — Presearch / Groundwork Capsule

**Generated:** 2026-07-20 · **Branch:** `feat/atlas-setup-ui` · **Method:** Groundwork brownfield pass (delta-scp orient → 3 parallel code-recon agents → firsthand verification of load-bearing claims).
**Purpose:** Hand this to Fable to fan out. Every workstream below is scoped, file-anchored, and has a tool-provable done-condition. No task is created from a hunch.

---

## 0. The verdict (read this first)

**Atlas is not a monster. It is a tractable core buried under removable litter, dead scaffolding, and three self-maps that disagree.**

- **The real code:** ~218,600 lines of TS/JS/Python across **~18 live services + 2 live apps**. Medium system.
- **The spine already exists and is clean:** one state store (delta-kernel `~/.delta-fabric/state.db`), three working front doors (atlas-map MCP · `atlas-ai` CLI · delta-kernel REST), and `atlas-map-api:3072` is a self-describing gateway that already knows **40 surfaces**. It's ~70% of the "harness" you want to complete.
- **The "loose and sloppy" feeling is real but shallow:** it's ~90% (a) invisible auto-started processes, (b) HTML/map duplication, (c) untracked root litter, and (d) dead scaffolding counted as if it were live. **Almost none of the high-leverage cleanup touches live code.**

The three things you named map to three concrete mechanisms, all diagnosed below with file:line.

---

## 1. The real shape

```
                          ┌─────────────────────────────────────────┐
   3 FRONT DOORS  ───────►│  atlas-map-api :3072  (self-describing   │
   • atlas-map MCP        │  gateway — knows 40 surfaces, /call,     │
   • atlas-ai CLI         │  /describe, /items backbone, MCP)        │  ← ~70% of the harness
   • delta-kernel REST    └───────────────────┬─────────────────────┘
     (~15 route families)                     │ reads/proxies
                                              ▼
   STATE SPINE  ───────►  delta-kernel :3001  ──►  ~/.delta-fabric/state.db   ← source of truth
        │  (tasks, goals, work queue, cycleboard, signals, governance)
        │
        ├─ cognitive-sensor results.db   (read directly by delta-kernel)
        ├─ droplist store / memory-hub   (REST routers)
        └─ optogon signals store
                                              ▲
   PRODUCT SURFACE  ─── apps/inpact :3006 ─────┘  (offline-first client, NO own store — syncs to :3001)
```

**Verified anchors:** state dir `services/delta-kernel/src/api/server.ts:51`; db path `src/cli/sqlite-storage.ts:44`; gateway `services/atlas-map-api/src/atlas_map_api/{gateway.py,describe.py,items.py}`; inPACT client `apps/inpact/js/api.js:6` + `backbone.js:6`.

**The core services (tracked file counts):** cognitive-sensor(273) · aegis-fabric(132) · delta-kernel(126) · droplist(95) · canvas-engine(82) · search-stack(57) · cortex(47) · optogon(41) · atlas-map-api(37) · openclaw(28, hollow) · uasc-executor(23, partial) · delta-scp(22) · triangulation(20, partial) · memory-hub(11) · ws-gateway(6, partial) · perception(25, **stub — all NotImplementedError**). Live apps: inpact(37) · lattice(18).

---

## 2. The three pains, diagnosed

### PAIN A — "Processes run that I'm unaware of"

The stack is **designed to be invisible**. Mechanism:

| Layer | What it is | Evidence |
|---|---|---|
| **`\Atlas-Autostart` Scheduled Task** | **Logon-triggered.** Boots the 12-service stack in **hidden PowerShell windows** on every login. You never press start. | `State=Ready, Trig=LogonTrigger` (verified); `scripts/start_atlas.ps1:58` `-WindowStyle Hidden` |
| **delta-kernel governance daemon** | Auto-starts with **no on/off switch**; runs **11 cron jobs**. The 60-second `work_queue` tick can create pending actions and **fire phone notifications** autonomously. | `server.ts:81` `daemon.start()` (no env gate, verified); jobs `governance_daemon.ts:71-81`; `notifyPhone` at `:21` |
| **7 enabled Scheduled Tasks** | All `State=Ready` (verified): `Atlas-Autostart`, `PreAtlas-DailyPipeline` (06:30), `PreAtlas-CycleboardRetry` (06:45), `PreAtlas-DropList-Daemon` (logon), `AtlasMapNightlyRefresh` (05:00), `Optogon Audit`, `PreAtlas-AgentOrchestratorReminder`. | `Get-ScheduledTask` (verified) |
| **Triple-fired morning pipeline** | cognitive-sensor pipeline is triggered **3×/morning** by independent schedulers: daemon `sensor_daily` 05:45 + `PreAtlas-DailyPipeline` 06:30 + `PreAtlas-CycleboardRetry` 06:45. Duplicate work / race. | `governance_daemon.ts:80` + 2 tasks |
| **Portless daemon arms** | droplist `--once` (via task) and atlas-execution-daemon `run_forever` (uasc, currently off) — a port scan never reveals these. | `services/uasc-executor/daemon.py:150-168`; `scripts/run_droplist_daemon.ps1` |
| **`Optogon Audit` task is broken** | Points into a throwaway git worktree `.claude\worktrees\vigorous-hoover-3db0c2\...` that can vanish. | agent-reported (verify before acting) |

**Net:** there is **no visible status surface** for any of it — only a `.atlas-logs\` folder. That is the whole reason it feels like ghosts in the machine.

### PAIN B — "Tabs spam Chrome and open constantly"

Three independent tab/window sources:

1. **Per-service `start.bat` files** open **visible `cmd /k` terminals** — `services/delta-kernel/start.bat` opens **3** (Delta API, Delta Web, Crucix OSINT :3117); `aegis-fabric/start.bat` opens more. (agent-reported)
2. **`.claude/launch.json` = 42 configs.** Every Claude Code `preview_start` opens a browser tab. This file is itself accumulated cruft — it points at scratchpad temp dirs (`mandelbulb-preview`, a session temp path, `launch.json:507`), external repos (STRUDEL, anatomy-saas, sibling delta-scp), and a **dangling** `mosaic-orch` cwd → `services/mosaic-orchestrator` which **no longer exists** (`launch.json:266`, verified — dir is under `_retired`).
3. **`start_atlas.ps1` opens 2 Chrome tabs** on boot (inPACT + substrate, `:105-107`).

### PAIN C — "Lots of static information / growing mudball"

The artifacts meant to *describe* the system have become part of the mudball.

- **3 inventories disagree, none matches git:** FLEET_INVENTORY.md says **20 services / 253k LOC**; `audit/system-index.json` (freshest) says **74 subsystems / 925k LOC**; git ground-truth is **~18 services / ~218k source LOC**. The freshest is the **most wrong** — 62% of its 925k LOC is one vendored blob (`tools/anatomy-research`, 571,924 LOC). Even the canonical map is untrustworthy.
- **5 map artifacts frozen at the identical timestamp 2026-04-14 16:13** (SYSTEM_MANIFEST.json, Pre_Atlas_System_Debrief.json, system-map.html, DATAFLOW_GRAPH.json, COMPONENT_GRAPH.json) — dead docs masquerading as maps, 3 months stale.
- **`system-map.html` forked into 4 copies; `wall.html` into 2; `system-map-data.js` into 3 drifting snapshots** (one is 5.8 MB, byte-duplicated in `apps/lattice/`). Only the root `system-map.html` reads delta-kernel live (`:696,706`).
- **Root is a 147-file dump-bucket:** 96 images (~90 untracked screenshots) + genuine garbage: files literally named `nul`, `10mb`, `10485760`, `err.log`, plus empty `tmp/` `dist/` `1010/` dirs. **All untracked** — `git clean` + `.gitignore` clears it, zero code risk.
- **~55 MB of untracked generated blobs loose in tree:** `docs_manifest.js` (47 MB), `.tags-services` (7 MB ctags), `audit/system-map-data.js` (5.8 MB).
- **Dead scaffolding counted as "system":** 12 stub apps (all committed 2026-07-07, wired to nothing, present only in generated catalogs + the closed-loops ledger) + `services/_retired` (mirofish, mosaic-dashboard, mosaic-orchestrator) + `apps/_retired` (ai-exec-pipeline, blueprint-generator, c110-trace, canvas-demo) = **181 files / ~31k LOC of dead code on disk** (verified dirs exist).
- **Config hygiene lags code hygiene:** code-as-furniture fixes landed (openclaw/config.py, memory-hub/stores.py), but `.env.example:22,24`, `atlas-manifest.yaml:444`, and `atlas-map.json` still name retired mirofish/mosaic-orchestrator.

### PAIN D (surfaced, not named) — There are TWO Atlas codebases

`C:\Users\bruke\atlas` is a **separate git repo** (own toplevel, own `atlas.db`, `agent.py`, `serve.py`, `registry.json` + 3 stale backups `registry.json.bak*`). It runs inside the stack as `:8887 atlas-substrate` (`start_atlas.ps1:33`) but lives **outside** `Pre Atlas`. Part of "how Atlas works" is in a repo you're probably not editing. **This needs a decision** (see §5).

---

## 3. Consolidation plan for Fable (fan-out ready)

Workstreams are grouped into waves. **Same wave = parallelizable** (independent files). Later wave depends on earlier. Each has a **DoD** that `/groundwork verify` can prove. Waves are ordered by *leverage ÷ risk* — Wave 0 is pure tidy with zero code risk.

### WAVE 0 — Litter & orphans (zero code risk, do first, fully parallel)

- **0.1 · Root litter sweep.** Delete garbage files (`nul`, `10mb`, `10485760`, `err.log`, empty `tmp/`,`dist/`,`1010/`), gitignore the ~90 untracked screenshots + `.gw-map-refresh.log`/`.sync_bridge.log`/`console-graph-errors.txt`.
  **DoD:** `git status --short | wc -l` drops to only intentional changes; `ls nul 10mb 10485760 err.log 2>/dev/null` returns empty.
- **0.2 · Gitignore the 55 MB of generated blobs** (`docs_manifest.js`, `.tags-services`, `**/system-map-data.js`).
  **DoD:** `git check-ignore docs_manifest.js .tags-services audit/system-map-data.js` returns all three.
- **0.3 · Reap orphan/duplicate processes + document kill switches.** Kill squatters (:8799 iTunes, :8765 bare http.server, leaked duplicate memory-hub/atlas-map-api PIDs). Note :5173 belongs to unrelated *noutube-native* Electron.
  **DoD:** a `scripts/reap_orphans.ps1` exists; after run, `Get-NetTCPConnection` shows no non-Atlas listener on Atlas ports.
- **0.4 · Fix broken `Optogon Audit` scheduled task** (points into a deletable worktree).
  **DoD:** `Get-ScheduledTask 'Optogon Audit'` action path resolves to a stable location or task is removed.

### WAVE 1 — Visibility (kill the "ghosts" feeling)

- **1.1 · Add a daemon on/off switch.** Gate `daemon.start()` behind an env flag (`GOVERNANCE_DAEMON=1`) at `services/delta-kernel/src/api/server.ts:81`; default documented.
  **DoD:** starting :3001 with the flag unset does not spawn the 11 cron jobs (grep logs for `DAEMON_HEARTBEAT` absent).
- **1.2 · Deduplicate the morning pipeline.** Pick ONE trigger for the cognitive-sensor pipeline; disable the other two of {daemon `sensor_daily` 05:45, `PreAtlas-DailyPipeline` 06:30, `PreAtlas-CycleboardRetry` 06:45}.
  **DoD:** only one scheduler references `run_daily.py`/`refresh.py` for the morning run.
- **1.3 · One visible status surface.** A single "what's running" view (extend `scripts/status_atlas.ps1` and/or an `atlas_status`-backed HTML) that lists: every service up/down, every Scheduled Task + trigger, the daemon's last heartbeat, orphans. This is the antidote to Pain A.
  **DoD:** `atlas-map-api /status` (or `status_atlas.ps1`) prints services + tasks + daemon heartbeat in one call; wired into the boot UI.
- **1.4 · Rationalize the launch/terminal spam.** Delete dangling `mosaic-orch` from `launch.json:250-267`; remove scratchpad/external-repo entries; make per-service `start.bat` files defer to `start_atlas.ps1` (hidden) instead of opening visible terminals.
  **DoD:** `grep mosaic-orchestrator .claude/launch.json` empty; launch.json entries all point at live in-repo cwds.

### WAVE 2 — Collapse the map/UI duplication (single source of truth)

- **2.1 · Declare ONE canonical inventory.** Fix `audit/build_system_index.py` to exclude vendored/research dirs (kill the 572k-LOC `tools/anatomy-research` inflation); delete the 5 frozen-April artifacts (SYSTEM_MANIFEST.json, Pre_Atlas_System_Debrief.json, system-map.html-if-static, DATAFLOW_GRAPH.json, COMPONENT_GRAPH.json).
  **DoD:** `audit/system-index.json` subsystem count ≈ real service count (~20, not 74); the 5 April files are gone; one generator owns the number.
- **2.2 · Collapse `system-map.html` (4→1) and `wall.html` (2→1).** Keep the root live copy that reads delta-kernel; delete `audit/`, `apps/lattice/`, `.groundwork/` static forks and their `system-map-data.js` snapshots.
  **DoD:** `find . -name system-map.html -not -path './node_modules/*'` returns 1; `find . -name 'system-map-data.js'` returns ≤1.
- **2.3 · Point all live views at `atlas-map-api:3072`** instead of static JS snapshots.
  **DoD:** remaining map UI fetches from `:3072`, not a checked-in `*-data.js`.
- **2.4 · Quarantine dead scaffolding.** Move the 12 dead stub apps + confirm `_retired` dirs are excluded from all generators/catalogs (or delete after a `git tag` archive).
  **DoD:** the 12 stubs no longer appear in `system-index.json`; `code-recon prior-art` confirms zero live references.

### WAVE 3 — Complete the harness (the "agent harness" you want)

- **3.1 · Make `atlas-map-api` drive UIs, not just describe them.** Enable `ui`/`websocket` surface invocation (currently returns 422, per `SELF_DESCRIBE.md:117`). This is the single missing brick between "registry that knows 40 surfaces" and "harness that operates them."
  **DoD:** `atlas_call(surface, capability)` succeeds for a `ui`-kind surface (no 422); a wall/map surface renders via the gateway.
- **3.2 · Refresh docs to reality.** Update `CLAUDE.md`, `README.md`, `SELF_DESCRIBE.md` from "10 surfaces / 1 REST family" to the real **40 surfaces / ~15 REST families**. The docs *undersell* the system, which is itself a cause of "I don't know how it works."
  **DoD:** `SELF_DESCRIBE.md` surface count matches `atlas_describe_list()` output.
- **3.3 · Resolve the two-repo split** (`C:\Users\bruke\atlas` substrate) — see decision D below. Depending on the call: merge into Pre Atlas, formalize as a declared external surface, or retire.
  **DoD:** the substrate is either in-repo or has a declared `atlas.surface.json` + documented boundary; the 3 stale `registry.json.bak*` are gone.
- **3.4 · Finish or formally shelve the partials/stubs:** perception (stub), uasc-executor, ws-gateway, triangulation. Each gets a decision + DoD or a dated deferral (code-as-furniture: no rotting).

---

## 4. Confidence ledger

| Claim | Confidence | Basis |
|---|---|---|
| 42 launch configs; hidden-window autostart; 12-service curated stack | **HIGH** | read `launch.json` + `start_atlas.ps1` firsthand |
| 7 scheduled tasks, all Ready; `Atlas-Autostart` logon-triggered | **HIGH** | `Get-ScheduledTask` firsthand |
| `daemon.start()` no env gate (server.ts:81) | **HIGH** | grep firsthand |
| Sibling `C:\Users\bruke\atlas` is separate git repo running :8887 | **HIGH** | `git rev-parse` + `ls` firsthand |
| Dangling `mosaic-orch` cwd in launch.json:266; 7 retired dirs on disk | **HIGH** | grep + `ls` firsthand |
| Inventory disagreement 20/74/~18; 572k-LOC blob inflation; root litter ledger | **HIGH** | agent ran `git ls-files`/`tokei`/`stat`; consistent with my index peek |
| 11 daemon jobs + intervals; `notifyPhone` on work_queue tick | **MED** | agent file:line (`governance_daemon.ts:71-81,21`) — re-verify per task |
| Per-service `start.bat` open visible terminals; `Optogon Audit` worktree drift | **MED** | agent-reported — verify before acting |
| atlas-map-api `ui` invocation returns 422 | **MED** | agent cited `SELF_DESCRIBE.md:117` — confirm at HEAD |

**Doctrine for Fable:** treat MED rows as leads, not facts. Each task re-verifies its own anchors via `/groundwork verify` before marking done. Absence claims need 2+ angles.

---

## 5. Decisions only you can make (answer before Fable fans out)

1. **The sibling `C:\Users\bruke\atlas` repo** — merge into Pre Atlas, keep as a declared external surface, or retire? (Changes Wave 3.3 scope entirely.)
2. **`Atlas-Autostart` logon task** — keep auto-boot on login, or switch to manual `start_atlas.bat`? (Changes Wave 1 posture: hide-well vs make-explicit.)
3. **The daemon's autonomous phone notifications** — keep on by default, or default-off behind the new switch? (Wave 1.1.)
4. **12 dead stub apps + `_retired` dirs** — hard-delete (with a `git tag` archive), or keep quarantined on disk? (Wave 2.4.)

---

*Next step: convert Waves 0–3 into a `fest` festival (one sequence per wave, tasks pre-anchored to the file:line above) so Fable executes against proof-gated done-conditions — or hand this doc to Fable directly. Wave 0 is safe to start immediately with zero code risk.*
