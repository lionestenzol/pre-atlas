# Thread Workflow Map — 2026-04-21

Read-only investigation. Maps the end-to-end thread lifecycle across every CLI and state
file in Pre Atlas, so a future `close` command can be designed against the real surface
instead of an assumed one.

---

## 0. The thread lifecycle (overview)

```
memory_db.json  ─┐
                 ├─► thread_scorer ──► rank/scan cards
                 │                     │
                 │                     ▼
                 │              atl decide <id> <VERDICT>
                 │              (writes thread_decisions.json + decisions.log)
                 │                     │
                 │                     ▼
                 │              atl harvest --from-decisions
                 │              (writes harvest/<id>_<slug>/*)
                 │                     │
                 │              [optional]
                 │              cycleboard parse  → concepts.{json,md}
                 │              cycleboard dump   → conversation.md
                 │              cycleboard verify → coverage.{json,md}
                 │                     │
                 │                     ▼
                 │              atl apply  ──► results.db loop_decisions
                 │              (also triggers auto_actor.py)
                 │                     │
                 │                     ▼
                 │              auto_actor  → POST /api/law/close_loop
                 └────►loops.py regenerates loops_latest.json (reads closed set)

                 POST /api/law/close_loop writes:
                   closures.json (registry+stats)
                   loops_latest.json (filter out)
                   loops_closed.json (append)
                   delta-kernel system_state entity (mode, metrics, streak)
                   timeline event CLOSURE_PROCESSED
```

Three parallel "close" paths converge on the same state but with different side effects:

| Path | Entry | Writes DB row | Writes closures.json | Writes loops_closed | Triggers auto_actor | Writes thread_decisions.json |
|---|---|---|---|---|---|---|
| **atl decide+apply** | `atl decide … ; atl apply` | Yes (batch) | Via auto_actor after apply | Via auto_actor | Yes (prompted) | Yes |
| **close_loop.py** | `python close_loop.py 143 CLOSE` | Yes (direct) | Yes (via POST) | Yes (via POST) | No | No |
| **atlas / atlas-ai (TS)** | `atlas close <id>` | No (never!) | Yes (via POST) | Yes (via POST) | No | No |
| **auto_actor** | Batch / scheduled | Yes | Yes (via POST) | Yes (via POST) | n/a | No |

Already a major reconciliation risk — see §5.

---

## 1. CLI entry-point map (writes)

### 1.1 `atl` — atlas_triage_cli.py
`services/cognitive-sensor/atlas_triage_cli.py`. Thin dispatcher + safety layer.

| Subcommand | Forwards to | Files written |
|---|---|---|
| `atl scan` | thread_scorer | stdout only |
| `atl rank` | thread_ranker | stdout; optional `--json` `--score-cards` output files |
| `atl themes` | code_themes | stdout |
| `atl winners` | theme_winners | stdout |
| `atl ideas` | idea_code_join | stdout (reads `thread_decisions.json`) |
| `atl show <id>` | thread_scorer --convo | stdout |
| `atl decide <id> <V> [--note]` | — | `thread_decisions.json` (atomic replace), `decisions.log` (append) |
| `atl undo [id]` | — | `thread_decisions.json`, `decisions.log` (UNDO entry) |
| `atl harvest` | harvester | `harvest/<id>_<slug>/{code_blocks.md, key_quotes.md, final_output.md, summary.md, manifest.json}` |
| `atl apply` | — | `results.db.bak-<ts>` (backup), inserts rows into `loop_decisions` table. Optionally runs auto_actor.py. |
| `atl rollback [--index N]` | — | restores `results.db` from backup |
| `atl log [--tail]` | — | stdout (reads `decisions.log`) |
| `atl status` | — | stdout (reads `thread_decisions.json`, counts `loop_decisions`) |
| `atl serve` | http.server | — |

**Verdicts accepted:** `MINE`, `KEEP`, `CLOSE`, `ARCHIVE`, `REVIEW`, `DROP`.
Note `MINE`/`KEEP`/`REVIEW`/`DROP` are **not** recognised by downstream
(loops.py / cognitive_api.py only look for `CLOSE` and `ARCHIVE`). See §4.

### 1.2 `close_loop.py` — legacy interactive triage
`services/cognitive-sensor/close_loop.py`.

| Call | Writes |
|---|---|
| `python close_loop.py` (triage_all) | For each decision: row in `loop_decisions`, POST to `http://localhost:3001/api/law/close_loop`. After batch: reruns `loops.py, completion_stats.py, export_cognitive_state.py, route_today.py, governor_daily.py`. |
| `python close_loop.py <id>` | Same for one loop, prompting. |
| `python close_loop.py <id> CLOSE\|ARCHIVE` | Direct write, POST, pipeline refresh. |
| `python close_loop.py --list` | Read-only; reads `loops_latest.json` minus DB-decided set. |

Accepts only `CLOSE` and `ARCHIVE`. Never touches `thread_decisions.json` or `decisions.log`.
Delta-kernel POST is fire-and-forget (swallows all errors). Always calls `refresh_pipeline()`
which rebuilds `loops_latest.json` **and** `cognitive_state.json`.

### 1.3 `atlas.py` — Python daily routing engine
`services/cognitive-sensor/atlas.py`.

Commands: `boot`, `status`, `next`, `loop`, `plan`, `close`.
`atlas.py close` is **end-of-day closeout for the daily routing engine**, not thread close.
It writes `atlas_state.json` setting `closed: true` + `closed_at`. Completely disjoint from
loop/thread closure.

**Overlap confusion:** there are three `atlas`es.
- `atlas.py` (Python) – daily routing, `atlas_state.json`.
- `atlas.ts` (TS) – browser-parity CLI, talks to delta-kernel API.
- `atl` (atlas_triage_cli.py) – triage/harvest pipeline.
All three are on the user's PATH context at different times.

### 1.4 `cycleboard` CLI — cycleboard/cli.ts
`services/cognitive-sensor/cycleboard/cli.ts`.

| Subcommand | Writes |
|---|---|
| `cycleboard state/loops/day/cognitive/directive/health/osint` | read-only (reads brain JSONs) |
| `cycleboard energy/finance/skills/network …` | POST delta-kernel signals API |
| `cycleboard close <id>` | POST `/api/law/close_loop` outcome=closed |
| `cycleboard archive <id>` | POST `/api/law/close_loop` outcome=archived |
| `cycleboard day create/block/done/goal/rate` | updates cycleboard state |
| `cycleboard task/win/journal` | delta-kernel API |
| `cycleboard refresh` | runs refresh pipeline |
| `cycleboard dump <id>` | spawns `dump_conversation.py` → `harvest/<id>_<slug>/conversation.md` |
| `cycleboard parse <id>` | spawns `parse_conversation.py` → `harvest/<id>_<slug>/concepts.{json,md}` |
| `cycleboard verify <id> <artifact>` | spawns `verify_coverage.py` → `harvest/<id>_<slug>/coverage.{json,md}` |

`close/archive` here bypasses `loop_decisions` table entirely — goes straight to
delta-kernel. Python-side consumers (loops.py, cognitive_api.py) do not see the result in
the DB.

### 1.5 `atlas` TS CLI — atlas.ts
`services/delta-kernel/src/cli/atlas.ts`.

Screens: `status, mode, directive, health, energy, finance, skills, network, cognitive,
osint, az, calendar, home, loops, close, archive, tasks, task, ideas, brief, day, routine,
journal, win, wins, weekly, reflect, timeline, stats, control, settings, start, stop,
refresh, dashboard, daemon`.

`atlas close <id>` / `atlas archive <id>` → POST `/api/law/close_loop`. Same bypass as
cycleboard CLI — no DB row, no thread_decisions entry.

### 1.6 `atlas-ai` TS CLI — atlas-ai.ts
`services/delta-kernel/src/cli/atlas-ai.ts`. JSON-native for LLM agents.

Commands: `state, loops, day, cognitive, directive, health, osint, energy, finance, skills,
network, close, archive, day-create, day-block, day-done, day-goal, day-rate, task, win,
journal, refresh, next, …compound: morning, close-stale, done, checkpoint, wrap, do,
process-inbox, research-queue, draft-responses, standup, weekly-briefing, idea-briefs,
knowledge, closure-reports, work`.

`cmdClose` / `cmdArchive` / `compoundCloseStale` / `compoundDone` all POST close_loop with
no DB write (lines 318, 324, 638, 738). **Auto-archive-stale** is especially important:
scans loops, decides any loop past a staleness threshold is archived, fires close_loop —
this is a silent write path the user may not realize is running.

### 1.7 Pipeline scripts (not CLIs but called by atl / close_loop)

| Script | Inputs | Outputs |
|---|---|---|
| `thread_ranker.py` | results.db | stdout table; optional `--json`, `--score-cards` JSON |
| `dump_conversation.py` | memory_db.json | `harvest/<id>_<slug>/conversation.md` (or `conversation_<id>.md` if no harvest dir) |
| `parse_conversation.py` | memory_db.json | `harvest/<id>_<slug>/concepts.{json,md}` |
| `verify_coverage.py` | harvest/<id>/concepts.json, artifact path | `harvest/<id>/coverage.{json,md}` (includes `artifact` field) |
| `harvester.py` | memory_db, thread_scorer | `harvest/<id>_<slug>/{code_blocks.md, key_quotes.md, final_output.md, summary.md, manifest.json}` |
| `batch_triage.py` | hardcoded list | `loop_decisions` rows + POST to delta-kernel |
| `auto_actor.py` | results.db, loops_latest.json, idea_registry | `auto_close_ledger.json`, `loop_decisions` rows, POSTs close_loop |
| `loops.py` | results.db, loops_closed.json | `loops_latest.json` |
| `completion_stats.py` | loop_decisions | stdout |
| `export_cognitive_state.py` | cognitive_api.py in-memory | `cognitive_state.json` (includes `closure.truly_closed`, `archived`, `closure_quality`, loops[]) |
| `route_today.py` | cognitive_state.json | mode + daily_directive.txt |
| `governor_daily.py` | cognitive_state.json | daily_brief.md, daily_payload.json, etc. |

### 1.8 delta-kernel closure endpoint
`services/delta-kernel/src/api/server.ts` lines 1055–1440. Two sites do the same thing:
internal `processClosureEvent()` helper + the HTTP route. Writes:
- `closures.json` (registry + stats)
- `loops_latest.json` (filter out the closed id)
- `loops_closed.json` (append)
- `system_state` entity via atomic delta (mode, metrics, streak_days, build_allowed)
- Timeline event `CLOSURE_PROCESSED`

Idempotency: refuses duplicate `loop_id`. **Requires `loop_id`** for physical closure;
without one, only closures.json/stats mutate.

---

## 2. State file inventory (for a single closed thread)

| File | Writer(s) | Readers |
|---|---|---|
| `results.db` `loop_decisions` (convo_id, decision, date) | atl apply, close_loop.py, auto_actor.py, batch_triage.py, decide.py | loops.py, completion_stats.py, cognitive_api.py, behavioral_memory.py |
| `thread_decisions.json` | atl decide / undo | atl status, atl ideas, harvester.py, idea_code_join.py |
| `decisions.log` (append-only TSV) | atl decide / undo | atl log |
| `loops_latest.json` | loops.py, delta-kernel close_loop | close_loop.py, auto_actor.py, atlas_agent, cognitive_api.py, build_dashboard.py, atlas TS readers, cycleboard brain build |
| `loops_closed.json` | delta-kernel close_loop | loops.py (as dedupe input) |
| `closures.json` (closures[], stats{}) | delta-kernel close_loop, governance_daemon (daily reset, streak) | atlas.py (read_closures), delta-kernel unified-state endpoints, streak UI |
| `cognitive_state.json` | export_cognitive_state.py | route_today.py, governor_daily.py, delta-kernel server (closure.open), atlas.py, atlas.ts |
| `cycleboard/brain/cognitive_state.json` | cycleboard_push.py | cycleboard CLI, cycleboard HTML |
| `harvest/<id>_<slug>/summary.md` | harvester | human read |
| `harvest/<id>_<slug>/manifest.json` (verdict, stats, outputs list) | harvester | none programmatic |
| `harvest/<id>_<slug>/concepts.json` | parse_conversation | verify_coverage |
| `harvest/<id>_<slug>/coverage.json` (convo_id, **artifact**, covered/partial/missing) | verify_coverage | human read only — **nothing consumes this** |
| `harvest/<id>_<slug>/conversation.md` | dump_conversation | human |
| `harvest/<id>_<slug>/code_blocks.md, key_quotes.md, final_output.md` | harvester | human |
| `auto_close_ledger.json` | auto_actor | auto_actor (self) |

---

## 3. Consumer map (who reads "closed")

| Consumer | Reads | Displays |
|---|---|---|
| `loops.py` | `loop_decisions` (CLOSE/ARCHIVE) + `loops_closed.json` | regenerates `loops_latest.json` |
| `cognitive_api.py` → `cognitive_state.json` | `loop_decisions` table | `closure.{open, truly_closed, archived, ratio, closure_quality}` and `loops[]` |
| `route_today.py` | `cognitive_state.json` | Mode (CLOSURE / MAINTENANCE / BUILD / SCALE) + `daily_directive.txt` |
| `governor_daily.py` | `cognitive_state.json` | `daily_brief.md` (Open loops / Decision ratio / Closure quality) |
| `close_loop.py show_state` | `cognitive_state.json`, `daily_directive.txt` | stdout summary |
| `atlas.py` | `cognitive_state.json`, `closures.json` | `boot`/`status`/`loop` summaries + streak |
| `atlas.ts showLoops` | `/api/state/unified` → `cognitive_state.loops` | CLI list |
| `atlas-ai cmdLoops` | `/api/state/unified` | JSON |
| `cycleboard showLoops` | brain/cognitive_state.json | CLI list |
| `dashboard.html` | various JSON | status panels |
| `atlas_boot.html` | delta-kernel `/api/state/unified` | web boot screen |
| `governance_daemon` | `closures.json` | daily-reset of closures_today, streak check, alerting |
| `behavioral_memory.py` | `loop_decisions` date | per-day closure snapshot table |

---

## 4. Gaps (artifact not linked to "closed")

1. **No field in `loop_decisions` for artifact path.** Schema is `(convo_id TEXT, decision TEXT, date TEXT)`. When `atl decide 487 MINE --note "AI-EXEC pipeline"` fires, the note goes to `thread_decisions.json`/`decisions.log` but never into the DB. Nothing downstream (cognitive_state, dashboards, route_today, governor_daily) knows that 487 produced `apps/ai-exec-pipeline`.
2. **`closures.json` does not carry artifact either.** Entry shape is `{ts, loop_id, title, outcome}`. The delta-kernel endpoint never asks for artifact on input.
3. **`loops_closed.json` — same.** `{loop_id, title, closed_at, outcome}`. No artifact pointer.
4. **`harvest/<id>/coverage.json` has `artifact` — but nothing else reads it.** Grep confirms no Python or TS reads that field anywhere outside verify_coverage itself. This is the one file that links thread to built code, and it's a dead end.
5. **`harvest/<id>/manifest.json` has no artifact field** and no coverage file reference. It is created at harvest time, before verify_coverage runs, and is never updated afterwards.
6. **`MINE` verdict has no downstream semantics.** Only `CLOSE`/`ARCHIVE` are consumed by loops.py, completion_stats, cognitive_api. A `MINE` decision sits in `thread_decisions.json` invisible to every metric. `MINE` is the single verdict that implies "I intend to build something from this thread" — and it is the most invisible verdict in the system.
7. **No "built" flag anywhere.** There is no boolean saying "thread 487 has been turned into code at path X." The existence of coverage.json is the closest implicit signal, and it requires filesystem probing per thread.
8. **Cycleboard / atlas TS close bypasses everything Python-side.** `atlas close <id>` writes only to `closures.json`, `loops_closed.json`, `loops_latest.json` (filter) and delta-kernel entity. The `loop_decisions` table is never touched. On next Python pipeline run, `loops.py` still picks up the loop_id from `loops_closed.json` as its dedupe source — so the loop correctly disappears from `loops_latest.json`. But `cognitive_api.py`'s `closure.truly_closed` / `archived` counts are derived from `loop_decisions` alone, so these "closes" do **not** increment the metric that drives mode routing.
9. **`daily_directive.txt` / `governor_daily.md` never reference harvests or artifacts.** The user reads daily briefs that list open loops but has no indication that any of those loops is already partially built.
10. **No verification check at close-time.** Nothing stops `atl apply` from marking 487 CLOSE before `verify_coverage 487 apps/ai-exec-pipeline` has run. Nothing compares the verdict to coverage status.

---

## 5. Duplicate / conflict writes (reconciliation risk)

1. **`loop_decisions` table has four writers:** `atl apply`, `close_loop.py`, `auto_actor.py`, `batch_triage.py`, plus legacy `decide.py`. Each has its own idempotency approach (atl checks existing, close_loop prints "already decided", auto_actor returns False on existing, batch_triage filters against a fetched set, decide.py just inserts). All ultimately INSERT — so there is no risk of overwrite, but there is risk of **skew between writers on decision values.** `auto_actor` decides `CLOSE`/`ARCHIVE` heuristically and races with user-driven `atl apply`.
2. **Two parallel close paths ("DB path" vs "delta-kernel path").** atl and close_loop.py write DB first, POST second (best-effort). atlas/cycleboard/atlas-ai TS CLIs POST only. Net effect: `closure.truly_closed` (DB-derived) and `closures.stats.total_closures` (delta-derived) **can and do diverge.** Demonstrated by current state: `closures.json` shows `total_closures: 1` while `thread_decisions.json` carries 24 decisions and `decisions.log` has many more.
3. **Two close_loop implementations in server.ts.** Lines 1055–1238 (`processClosureEvent`) and 1255–1440 (the HTTP route) duplicate the whole body (closures.json read, idempotency, ratio, mode, streak, physical closure). They can drift.
4. **`loops_latest.json` has two writers.** `loops.py` rebuilds it from the DB; delta-kernel `close_loop` filters it in place. If both run out of order (e.g., delta-kernel close, then loops.py rebuild before DB row is present), the closed loop reappears in loops_latest until the next refresh. The comment in loops.py acknowledges this and uses `loops_closed.json` as a second dedupe source — but this only works if the delta-kernel path was taken. If `atl apply` wrote a DB row but its best-effort POST failed silently, `loops_closed.json` will not have the id and `loops.py` still uses the DB row, so the result is correct — but there is no parity check.
5. **`thread_decisions.json` vs `loop_decisions` table.** `atl status` shows both counts side-by-side, but nothing enforces that they agree. The user can `atl decide` without `atl apply`, leaving JSON with decisions that the metrics never see. Or `batch_triage.py` can insert DB rows with no JSON counterpart.
6. **`closures.json.stats.streak_days` vs `system_state.streak_days` in delta-kernel.** Both are mutated in the same handler, but the increment is conditional on "BUILD/SCALE mode after this closure" — that computed mode depends on `openLoops` read from `cognitive_state.json`, which is a snapshot. If `cognitive_state.json` is stale, streak math is wrong.
7. **cycleboard/brain/cognitive_state.json vs services/cognitive-sensor/cognitive_state.json.** Two files, same name, written by different processes (cycleboard_push copies after export). A "closed" thread appears in one before the other.

---

## 6. Archive / delete audit

User concern: "I always close first and that's how I end up with everything archived and deleted."

**Finding: nothing in the thread workflow physically deletes or moves files.** `archive` is purely a row-level tag (`decision='ARCHIVE'` in `loop_decisions`) and/or a closures.json entry with `outcome='archived'`. `harvest/<id>_<slug>/` is never deleted by any close path. `memory_db.json` is never mutated.

What actually happens on ARCHIVE:
1. Row `(convo_id, 'ARCHIVE', date)` inserted into `loop_decisions`.
2. `loops.py` excludes it on next run → vanishes from `loops_latest.json`.
3. `cognitive_api.py` counts it in `closure.archived`, subtracts it from `open`.
4. `route_today.py` can route to CLOSURE mode if `closure_quality < 30%` ("archiving is not closing"). Directive becomes *"Pick 1 archived loop and actually finish it."*
5. If delta-kernel was called: entry in `closures.json`, `loops_closed.json`, delta entity.

What **does not** happen:
- No file deletion.
- No move to `_archive/`.
- No mutation of `thread_decisions.json` (record stays forever).
- No mutation of `memory_db.json`.
- No mutation of harvest dir.

However, two subtle "loss" vectors:
- **Invisibility-as-loss.** A closed/archived thread disappears from `loops_latest.json`, the one file every dashboard, daily brief, atl status, atlas-ai state call, and the main atlas UI reads. The user sees "gone." From the surfaces they look at every day (`daily_directive.txt`, `governor_daily.md`, atlas_boot.html) the thread is effectively deleted. The only way back to it is to remember the convo_id and grep `harvest/`, `thread_decisions.json`, `decisions.log`, or the `loop_decisions` table.
- **Auto-archive-stale silently kills loops.** `atlas-ai compoundCloseStale` (server.ts L638 and elsewhere) fires `close_loop` on stale loops with reason `"atlas-ai auto-archive (stale)"`. Nothing surfaces "N loops were auto-archived today." Any loop that had an in-progress harvest or an un-verified artifact can vanish this way.
- `atl rollback` only restores `results.db` — not `thread_decisions.json`, `closures.json`, `loops_closed.json`, `cognitive_state.json`. A rollback undoes the metric but not the delta-kernel-side closure, creating another drift vector.

In short: **nothing deletes, but almost every daily surface silently hides anything closed, and there is no surface that shows "closed threads with artifacts vs closed threads without."**

---

## 7. Worked example — thread 487

**Thread 487** = "AI Execution Pipeline" ChatGPT conversation. User decided `MINE` on
2026-04-21 12:30:16 (from `decisions.log`).

State trail today:

| File | Entry | Links back to 487 | Links forward to built code |
|---|---|---|---|
| `memory_db.json[487]` | 268 msgs, 620,561 chars | — | — |
| `thread_decisions.json.decisions[…]` | `{convo_id:"487", verdict:"MINE", note:"AI Execution Pipeline multi-stack build. 87 Python + 85 jsx + 82 bash + 1 Dart. Extract as AI-EXEC pipeline repo.", decided_at:"2026-04-21T12:30:16"}` | convo_id | note contains the intent but no artifact path |
| `decisions.log` | Append-only line with same data | convo_id | same note |
| `harvest/487_marketing-for-beginners/manifest.json` | `{convo_id:"487", verdict:"MINE", harvest_dir:"harvest\\487_marketing-for-beginners", stats:{total_blocks:300, unique_blocks:298, …}}` | convo_id | **none** — no artifact field |
| `harvest/487_marketing-for-beginners/summary.md` | verdict `MINE`, topics, classification | convo_id | none |
| `harvest/487_marketing-for-beginners/code_blocks.md` | 298 unique blocks | convo_id | none |
| `harvest/487_marketing-for-beginners/concepts.json` | concept checklist from parse_conversation | convo_id | none |
| `harvest/487_marketing-for-beginners/coverage.json` | `{convo_id:487, artifact:"apps\\ai-exec-pipeline", summary:{covered:10, partial:6, missing:27, unverifiable:0}, rows:[…]}` | convo_id | **artifact path present — the only link in the system** |
| `harvest/487_marketing-for-beginners/coverage.md` | human-readable table | convo_id | artifact in prose |
| `apps/ai-exec-pipeline/{README.md, pipeline.py, server.py, client.py, data/, static/, requirements.txt}` | the built code | **nothing back-references 487** | n/a |
| `results.db.loop_decisions` | — | **absent** (verdict is MINE; no DB row was written because MINE is not CLOSE/ARCHIVE) | n/a |
| `cognitive_state.json` | 487 still counted as `closure.open` | — | — |
| `loops_latest.json` | 487 still present if score ≥ threshold | — | — |
| `closures.json` | no 487 entry | — | — |
| `loops_closed.json` | empty `[]` | — | — |
| `governor_daily.md` | "Open loops: N" — 487 still in the count | — | — |

**Summary of 487's state:** the thread has been harvested, parsed, verified against
`apps/ai-exec-pipeline` with 10 covered / 6 partial / 27 missing concepts, and the
artifact path is sitting in one JSON file. But:
- Nothing outside `harvest/487_*/coverage.json` knows the artifact exists.
- The thread is **still an "open loop"** from every metric's perspective (MINE verdict is invisible to loop_decisions, closures.json, and cognitive_state).
- If the user runs `atl apply` without first adding `CLOSE` or `ARCHIVE`, 487's `MINE` verdict is still a no-op for the loop counter.
- If the user runs `atlas close 487` (TS CLI), it POSTs to delta-kernel which writes `closures.json` + `loops_closed.json` but still never links to `apps/ai-exec-pipeline`.
- Any future developer (or Claude session) loading `loops_latest.json` or `cognitive_state.json` will see 487 as unfinished work even though 298 of its 300 code blocks are in a running service.

This is the exact failure mode a `close` command must solve.

---

## 8. Design surface (for the future `close` command — inputs only, not proposals)

A redesigned `close <id> [--artifact <path>]` would need to:

Write to:
- `loop_decisions` (row, so cognitive_api.closure counts update)
- `thread_decisions.json` + `decisions.log` (audit trail)
- `closures.json` via delta-kernel POST (mode routing + streak)
- `loops_latest.json` / `loops_closed.json` (physical filter, handled by delta-kernel if loop_id provided)
- `harvest/<id>_<slug>/manifest.json` (add `artifact` + `closed_at`)
- System_state delta (handled by delta-kernel)

Verify before marking done:
- `harvest/<id>_<slug>/coverage.json` exists and either `missing == 0` or user confirmed.
- Artifact path exists on disk.
- No existing `loop_decisions` row for this convo_id (unless `--force`).

Surface the fact of "built":
- Add `artifact` field to one or more of: `loop_decisions` (new column), `closures.json` entry, `loops_closed.json` entry, `cognitive_state.closure.built[]` list.
- Expose it in `atl status`, `atlas.ts loops`, `governor_daily.md`, `cognitive_state` output.

Reconcile writers:
- Single authority that writes both DB row and POST (currently only `close_loop.py` does both).
- atl TS CLIs must either stop bypassing the DB, or an ingress watcher must mirror `closures.json` into `loop_decisions`.

These are surface requirements, not a design.

---

## 9. File:line index of every write

For fast lookup when designing the close command:

- `atlas_triage_cli.py:53–70` — `_save_decisions_atomic` → `thread_decisions.json`
- `atlas_triage_cli.py:73–75` — `_journal_append` → `decisions.log`
- `atlas_triage_cli.py:240–256` — `cmd_apply` → `results.db` loop_decisions, backup
- `close_loop.py:221–226` — INSERT into loop_decisions
- `close_loop.py:232–245` — POST /api/law/close_loop
- `close_loop.py:253–272` — `refresh_pipeline` runs 5 scripts
- `auto_actor.py:152–187` — record_decision DB + POST
- `auto_actor.py:343–345` — auto_close_ledger.json write
- `decide.py:46` — INSERT into loop_decisions (legacy)
- `batch_triage.py:42–44` — INSERT
- `harvester.py:135,151,169,209,234` — 5 files per harvest dir
- `parse_conversation.py:285–286` — concepts.{json,md}
- `verify_coverage.py:311–312` — coverage.{json,md}
- `dump_conversation.py:86` — conversation.md
- `loops.py:66` — atomic_write `loops_latest.json`
- `export_cognitive_state.py:17` — `cognitive_state.json`
- `server.ts:1148` — closures.json (internal helper)
- `server.ts:1159,1165` — loops_latest, loops_closed (internal helper)
- `server.ts:1210–1211` — saveEntity + appendDelta
- `server.ts:1386` — closures.json (HTTP route)
- `server.ts:1400,1415` — loops_latest, loops_closed (HTTP route)
- `cycleboard/cli.ts:315–327` — close/archive (POST only)
- `atlas.ts:331–343` — closeLoop (POST only)
- `atlas-ai.ts:315,321,638,738` — close/archive/auto-archive/auto-close (POST only)

---
End of map. No close command proposed here — this file describes surface only.
