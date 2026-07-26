# Pre Atlas CLI Map

_Auto-generated 2026-06-20 by `audit/imports/_build_cli_map.py`. For agents — what each CLI is and exactly how to invoke it._  
_45 CLIs · {'command-cli': 13, 'infra-tool': 4, 'one-shot-script': 28}_

Static-extracted. Entries marked ✓ are enriched from the hand-curated `services/cognitive-sensor/cli_manifest.json`; the rest are AST-extracted (command lists are real, descriptions come from module docstrings).

## Command CLIs (subcommand dispatch — the ones to actually drive)

| CLI | Invoke | Cmds | What it does |
|---|---|---|---|
| ✓ **`atl`** | `atl --help` | 23 | Primary thread triage CLI. Walks a thread through the lifecycle (HARVESTED -> PLANNED -> BUILDING -> REVIEWING -> DONE/RESOLVED/DROPPED). |
| ✓ **`atlas`** | `python atlas.py --help` | 6 | Daily routing engine. Energy -> mode -> next-action. NOT related to thread triage. |
| ✓ **`atlas-ai.ts`** | `npx tsx services/delta-kernel/src/cli/atlas-ai.ts help` | 10 | AI-native JSON-in/JSON-out CLI. Primitives + compound commands. All output is {ok, data\|error}. Guarded: autonomous closers check midLifecy |
| ✓ **`atlas.ts`** | `npx tsx services/delta-kernel/src/cli/atlas.ts help` | 27 | Unified human TypeScript CLI. 21 screens. All go through delta-kernel /api/state/unified. |
| **`atlas_approve`** | `python services/cognitive-sensor/atlas_approve.py --help` | 3 | CLI to approve/deny auto_actor proposals and fire the runner. |
| **`atlas_cli`** | `python tools/atlas-cli/src/atlas_cli/main.py --help` | 10 | atlas — CLI front-end over atlas-map-api (:3072). |
| ✓ **`atlas_cli`** | `python atlas_cli.py --help` | 5 | Single entry point that runs the full daily/weekly pipelines via AtlasAgent. |
| **`atlas_query`** | `python services/cognitive-sensor/atlas_query.py --help` | 21 | atlas_query.py — Headless CLI access to the Cognitive Atlas. |
| ✓ **`auto_actor`** | `python auto_actor.py --help` | 1 | Autonomous closer + directive executor. Guarded: skips any thread with manifest.status in mid-lifecycle or terminal. |
| ✓ **`close_loop`** | `python close_loop.py --help` | 5 | Manual close/archive of a single loop + pipeline refresh. |
| ✓ **`cycleboard`** | `npx tsx services/cognitive-sensor/cycleboard/cli.ts help` | 11 | CycleBoard terminal CLI. Day plans, concept dumps, coverage audits, lifecycle board. |
| **`delta`** | `npx tsx services/delta-kernel/src/cli/index.ts help` | 0 | Delta-State Fabric — CLI Entry Point  Run with: npx tsx src/cli/index.ts |
| **`droplist`** | `python services/droplist/droplist/cli.py --help` | 32 | drop CLI. |

## Infra / generator tools

| CLI | Invoke | Cmds | What it does |
|---|---|---|---|
| **`_build_cli_map`** | `python audit/imports/_build_cli_map.py --help` | 0 | Build a complete CLI map for the repo — for agents, not humans. |
| **`_build_map`** | `python audit/imports/_build_map.py --help` | 3 | Build a system map for any repo. |
| **`validate`** | `python contracts/validate.py --help` | 1 | validate.py — Optogon stack contracts validator. |
| **`write_fest_tasks`** | `python doctrine/scripts/write_fest_tasks.py --help` | 3 | write_fest_tasks.py Materializes the optogon-stack festival task body markdown files. |

## One-shot scripts (28) — flag-only, run individually

_Not subcommand CLIs. Each takes flags; `<script> --help` for its surface. Listed in `cli-map.json` with extracted flags._

| Directory | Count |
|---|---|
| `services/cognitive-sensor/` | 21 |
| `tools/fest-reconcile/` | 4 |
| `tools/codex-partner/` | 1 |
| `./` | 1 |
| `services/uasc-executor/` | 1 |

---

## Command surfaces (command-CLIs)

### `atl` — services/cognitive-sensor/atlas_triage_cli.py
Invoke: `atl --help`  

- `help` — Extended command guide.
- `scan` — Score open loops by abandonment.
- `rank` — Rank threads by value signal.
- `themes` — Cluster themes across threads.
- `winners` — Show top-ranked threads.
- `ideas` — Ideas extracted from conversations.
- `harvest` — Write harvest/<id>_*/manifest.json with summary, code, quotes, concepts. Sets status=HARVESTED.
- `show` — Show harvest dir contents.
- `decide` — Record verdict (MINE|CLOSE|ARCHIVE|KEEP|REVIEW|DROP). Appends thread_decisions.json.
- `undo` — Reverse the most recent decision.
- `apply` — Flush pending decisions to results.db loop_decisions and run auto_actor.
- `rollback` — Rollback the last apply.
- `log` — Tail decisions.log.
- `status` — Show lifecycle status for a thread or the whole triage queue.
- `serve` — Local HTTP server for the triage UI.
- `plan` — Interactive MUST/NICE/SKIP classification of concepts. Writes build_plan.json. Sets status=PLANNED.
- `start` — Declare the artifact being built. Sets status=BUILDING + artifact_path + building_started_at.
- `review` — Run verify_coverage against build_plan.json. Sets status=REVIEWING + coverage_score + reviewed_at.
- `done` — Terminal DONE for MINE verdict. Gates on coverage >= 0.8 and zero missing MUST items. POSTs full-shape close_loop payload.
- `resolve` — Terminal RESOLVED for CLOSE verdict (no artifact needed).
- `drop` — Terminal DROPPED for ARCHIVE verdict (no artifact needed).
- `lifecycle` — Show full state-machine trace for one thread.
- `in-progress` — List threads in PLANNED|BUILDING|REVIEWING.

### `atlas` — services/cognitive-sensor/atlas.py
Invoke: `python atlas.py --help`  

- `boot` — Start the day. Derive mode from energy + open loops.
- `status` — Current mode / energy / closures.
- `next` — Print the single next action.
- `loop` — Top open loops for today.
- `plan` — Midday recalculation.
- `close` — End-of-day closeout. Flips state.closed=true.

### `atlas-ai.ts` — services/delta-kernel/src/cli/atlas-ai.ts
Invoke: `npx tsx services/delta-kernel/src/cli/atlas-ai.ts help`  

- `state` — Full system snapshot.
- `next` — Recommended action based on mode/energy.
- `do` — Decide + execute with work admission. Autonomous guard applies.
- `morning` — Start-of-day compound: plan + blocks + baseline goal.
- `close-stale` — Batch archive stale low-value loops. Guarded by midLifecycleIds(). Returns skipped_mid_lifecycle count.
- `close` — Close one loop. Sends status=RESOLVED.
- `archive` — Archive one loop. Sends status=DROPPED.
- `done` — Mark a time block complete + log win.
- `wrap` — End-of-day wrap. Rating + journal.
- `weekly-reflect` — Weekly reflection aggregate.

### `atlas.ts` — services/delta-kernel/src/cli/atlas.ts
Invoke: `npx tsx services/delta-kernel/src/cli/atlas.ts help`  

- `home` — Full dashboard (mode, plan, signals, ideas, pulse).
- `status` — System status.
- `mode` — Current routing mode.
- `loops` — Open loops with status badges + artifact links.
- `lifecycle` — In-progress + finished-today board (reads brain/lifecycle_board.json).
- `close` — Close a loop. Sends status=RESOLVED.
- `archive` — Archive a loop. Sends status=DROPPED.
- `brief` — Today's daily brief.
- `weekly` — Weekly governor packet.
- `cognitive` — Cognitive drift radar.
- `refresh` — Run refresh pipeline.
- `dashboard` — Rebuild dashboard.html.
- `day` — Today's plan and blocks.
- `journal` — Journal entries.
- `wins` — Recent wins.
- `timeline` — Recent system events.
- `stats` — Statistics.
- `settings` — System settings.
- `energy` — Energy signals.
- `finance` — Finance signals.
- `skills` — Skills signals.
- `network` — Network signals.
- `tasks` — Task list.
- `ideas` — Idea registry.
- `osint` — OSINT feed.
- `control` — Control panel.
- `daemon` — Daemon status / control.

### `atlas_approve` — services/cognitive-sensor/atlas_approve.py
Invoke: `python services/cognitive-sensor/atlas_approve.py --help`  

- `list` — show pending proposals
- `approve` — approve + fire runner
- `deny` — mark as denied

### `atlas_cli` — tools/atlas-cli/src/atlas_cli/main.py
Invoke: `python tools/atlas-cli/src/atlas_cli/main.py --help`  

- `where` — Which subsystem owns the current working directory?
- `locate` — Which subsystem owns the given file?
- `neighbors` — List N-hop dependency neighbors.
- `path` — Shortest directed dependency path between two subsystems (both ways).
- `search` — Fuzzy match across name + purpose + language + framework.
- `status` — Live signals: autostart + ported + retired.
- `list-systems` — List subsystems (filter by group or autostart membership).
- `show` — Detail for one subsystem (+ depends_on / depended_on_by).
- `reload` — Re-read system-index.json + atlas-map.json from disk.
- `open` — Open system-map.html in your default browser (optionally focused on a node).

### `atlas_cli` — services/cognitive-sensor/atlas_cli.py
Invoke: `python atlas_cli.py --help`  

- `daily` — Run daily loop: refresh + governor brief.
- `weekly` — Run weekly loop: daily + audit + packet.
- `backlog` — Idea pipeline + backlog maintenance.
- `briefs` — Regenerate briefs only (no data refresh).
- `status` — File freshness + system status.

### `atlas_query` — services/cognitive-sensor/atlas_query.py
Invoke: `python services/cognitive-sensor/atlas_query.py --help`  

- `stats` — Top-bar stats (messages, clusters, noise, etc.)
- `layers` — List available layer toggles
- `vectors` — Group clusters by asset_vector
- `clusters` — List all clusters
- `cluster` — Full cluster record (Inspector view)
- `inspect` — Alias for `cluster`
- `leverage` — Leverage Ranking table
- `search` — Find clusters whose titles/ngrams mention QUERY
- `near` — Cosine-nearest clusters to CLUSTER_ID
- `convo` — Find what cluster a conversation belongs to
- `messages` — All conversations in a cluster with titles, dates, topic words (joins results.db)
- `themes` — Cross-cluster topic threads (themes that span multiple clusters)
- `region` — Spatial neighborhood around a cluster (within cosine radius)
- `graph` — Full sigma graph (nodes + edges) or --summary for shape
- `graph-node` — One cluster's graph node + all incident edges
- `bridges` — Most-connected clusters (high graph degree)
- `path` — Shortest path in cluster graph from A to B
- `evolution` — Time histogram of a cluster (oldest..newest in 10 bins)
- `role-breakdown` — User/assistant/tool split inside a cluster
- `density` — Spatial density per cluster (UMAP 2D space)
- `text` — Pull actual message text of a conversation from the ChatGPT export bundle

### `auto_actor` — services/cognitive-sensor/auto_actor.py
Invoke: `python auto_actor.py --help`  

- `(no args)` — Run one full cycle.

### `close_loop` — services/cognitive-sensor/close_loop.py
Invoke: `python close_loop.py --help`  

- `(no args)` — Interactive triage of all open loops.
- `--list` — Print open loops, no action.
- `<id>` — Analyze one loop and recommend.
- `<id> CLOSE` — Close now. Sends status=RESOLVED.
- `<id> ARCHIVE` — Archive now. Sends status=DROPPED.

### `cycleboard` — services/cognitive-sensor/cycleboard/cli.ts
Invoke: `npx tsx services/cognitive-sensor/cycleboard/cli.ts help`  

- `today` — Show today's plan.
- `calendar` — Month grid.
- `week` — Week overview.
- `plan` — Create a day plan.
- `complete` — Toggle time block N.
- `add` — Add custom event.
- `status` — System overview.
- `lifecycle` — In-progress + finished-today (from brain/lifecycle_board.json).
- `dump` — Dump full ChatGPT transcript.
- `parse` — Extract concept checklist.
- `verify` — Coverage audit: does an artifact cover a thread's concepts?

### `delta` — services/delta-kernel/src/cli/index.ts
Invoke: `npx tsx services/delta-kernel/src/cli/index.ts help`  

_(no subcommands extracted — flag-only or parse-failed)_

### `droplist` — services/droplist/droplist/cli.py
Invoke: `python services/droplist/droplist/cli.py --help`  

- `input`
- `--ship`
- `--recent`
- `--show`
- `--memory-search`
- `--external`
- `--morning`
- `--review`
- `--domain`
- `--status`
- `--needs-decision`
- `--inventory`
- `--hash`
- `--ship-from`
- `--graph`
- `--brief`
- `--watch`
- `--entities`
- `--recurring-add`
- `--json`
- `--no-color`
- `input`
- `--json`
- `--no-color`
- `--recent`
- `--domain`
- `--status`
- `--needs-decision`
- `--no-color`
- `folder`
- `--hash`
- `drop_id`
