# Lifecycle Propagation & CycleBoard Visibility — Gap Map

**Date:** 2026-04-21
**Scope:** Read-only audit. No code changes.
**Source of truth for correct shape:** [docs/thread-lifecycle.md](thread-lifecycle.md) + `services/delta-kernel/src/api/server.ts:1255-1338` (close_loop zod schema + closureEntry).

## Current state confirmation

`services/cognitive-sensor/closures.json` has 2 entries:

| # | loop_id | keys present | shape |
|---|---|---|---|
| 0 | (pre-487) | `ts, loop_id, title, outcome` | OLD |
| 1 | `487` | `ts, loop_id, title, outcome, artifact_path, coverage_score, status` | NEW |

Entry 1 (487) verbatim:
```json
{"ts":1776800725547,"loop_id":"487","title":"Marketing for Beginners","outcome":"closed","artifact_path":"apps/ai-exec-pipeline","coverage_score":0.186,"status":"DONE"}
```

Manifest `harvest/487_marketing-for-beginners/manifest.json`: `status=DONE`, `artifact_path=apps/ai-exec-pipeline`, `coverage_score=0.186`, `building_started_at / reviewed_at / done_at` all populated.

Server schema accepts `{loop_id?, title?, outcome (required, "closed"|"archived"), artifact_path?, coverage_score? ∈[0,1], status? ∈ DONE|RESOLVED|DROPPED}` and always writes a closureEntry with all seven fields (missing ones nulled).

---

## 1. Legacy closure writers (old-shape leaks)

| File | Line | Current payload | Should send | Trigger | Has new fields? |
|---|---|---|---|---|---|
| [close_loop.py](../services/cognitive-sensor/close_loop.py) | 234 | `{loop_id, title, outcome}` | `+ artifact_path:null, coverage_score:null, status:"RESOLVED"` (CLOSE) / `status:"DROPPED"` (ARCHIVE) | Manual CLI: `python close_loop.py <id> CLOSE\|ARCHIVE`. Also INSERTs `loop_decisions` row, then `refresh_pipeline()` runs loops.py → completion_stats.py → export_cognitive_state.py → route_today.py → governor_daily.py | NO |
| [atlas-ai.ts](../services/delta-kernel/src/cli/atlas-ai.ts) `cmdClose` | 318 | `{loop_id, outcome:"closed", title:"atlas-ai close"}` | `+ status:"RESOLVED"` | Manual: `atlas-ai close <id>` | NO |
| atlas-ai.ts `cmdArchive` | 324 | `{loop_id, outcome:"archived", title:"atlas-ai archive"}` | `+ status:"DROPPED"` | Manual: `atlas-ai archive <id>` | NO |
| atlas-ai.ts `auto-archive-stale` | 638 | `{loop_id, outcome:"archived", title:"atlas-ai auto-archive (stale)"}` | `+ status:"DROPPED"` **AND** pre-check `manifest.status` — skip if ∈ {PLANNED, BUILDING, REVIEWING} | Batch loop in `cmdAutoArchiveStale`. Callable from UI / scheduled. **HIGHEST-RISK leak.** | NO |
| atlas-ai.ts `auto-close` decision | 738 | `{loop_id, outcome:"closed", title:"atlas-ai auto-close"}` | `+ status:"RESOLVED"` + manifest guard | Autonomous executor when decision.action = `close-loop` | NO |
| [atlas.ts](../services/delta-kernel/src/cli/atlas.ts) `closeLoop` | 334 | `{loop_id, outcome, title:"CLI ${outcome}"}` | `+ status` (RESOLVED/DROPPED) | Manual: human `atlas close/archive <id>` | NO |
| atlas_triage_cli.py `cmd_done` | ~616 | `{loop_id, title, outcome, artifact_path, coverage_score, status:"DONE"}` | ✅ correct | `atl done <id>` | YES (reference impl) |
| atlas_triage_cli.py `_resolve_or_drop` | ~640 | new shape with status RESOLVED/DROPPED | ✅ correct | `atl resolve / atl drop` | YES (reference impl) |
| batch_triage.py | — | does not POST close_loop (produces recs only) | n/a | n/a | n/a |
| decide.py | — | does not POST close_loop | n/a | n/a | n/a |

**Net:** 6 legacy POST sites (1 Python + 5 TS). Only `atl` (triage CLI) is correct.

---

## 2. Closure readers (blind consumers)

Zero readers surface `artifact_path`, `coverage_score`, `status`, or mid-lifecycle states (HARVESTED / PLANNED / BUILDING / REVIEWING).

| Reader | Reads from | Extracts | Should also read | Surface |
|---|---|---|---|---|
| [cycleboard/cli.ts](../services/cognitive-sensor/cycleboard/cli.ts) | `/api/cycleboard`, `/api/state/unified` | `open_loops`, `closure_ratio`, `closures_today`, `streak_days`, `loops[0].title` | `artifact_path`, `status`, in-progress counts | Terminal CLI time-block view |
| [cycleboard/index.html](../services/cognitive-sensor/cycleboard/index.html) | shell only; JS modules consume `brain/*.json` | n/a | a new panel fed by closures + manifest | Browser dashboard |
| [wire_cycleboard.py](../services/cognitive-sensor/wire_cycleboard.py) | copies `cognitive_state.json`, `daily_directive.txt`, `daily_payload.json`, `governance_state.json`, `governor_headline.json`, `prediction_results.json`, `idea_registry.json` → `cycleboard/brain/` | whole-file copies | also copy `closures.json` + emit derived `lifecycle_board.json` | run_daily.py Phase 4.5 |
| `cycleboard/brain/*.json` | closures.json **NOT** among them today | n/a | add `lifecycle_board.json` | dashboard data |
| [atlas.ts](../services/delta-kernel/src/cli/atlas.ts) (20/21 screens) | `/api/state/unified` | `open_loops`, `closure_ratio`, `loops[].{convo_id,title,score}`, `cogState.closure.closure_quality` | per-closure artifact links; in-progress counts; a **Lifecycle** screen | Human CLI |
| [governor_daily.py](../services/cognitive-sensor/governor_daily.py) | `cognitive_state.json`, `idea_registry.json`, `completion_stats.json` | `closure.ratio/open/closure_quality/truly_closed` | avg `coverage_score`, status distribution, artifact count | `daily_brief.md`, `governor_headline.json` |
| [governor_weekly.py](../services/cognitive-sensor/governor_weekly.py) | `governance_state.json`, `idea_registry.json` | `active_lanes`, `lane.status/name` | artifacts shipped this week, avg coverage, DONE/RESOLVED/DROPPED counts | `weekly_governor_packet.md` |
| [export_cognitive_state.py](../services/cognitive-sensor/export_cognitive_state.py) | delegates to `cognitive_api.py` | n/a | include per-loop `status`, `artifact_path` | `cognitive_state.json` |
| [dashboard.html](../services/cognitive-sensor/dashboard.html) | pre-rendered snapshot | top 10 open loops, closure counts | artifact column, lifecycle badges | static HTML |

---

## 3. `atlas.py` verdict — **KEEP** (unrelated tool)

Confusingly named but NOT a triage tool. 364 lines. Commands: `boot / status / next / loop / plan / close`, where `plan` is **midday energy recalculation** and `close` is **end-of-day closeout** (sets `state["closed"] = True` in `cognitive_state.json` — nothing more).

- Overlap with `atl`? **None.** `atl` transitions thread lifecycle; `atlas.py` routes the daily cycle (energy → mode → next_action).
- Writes `thread_decisions.json` / `loop_decisions` / POSTs `close_loop`? **No / no / no.** `cmd_close` only flips the day-state flag.
- Launcher? [atl.cmd](../services/cognitive-sensor/atl.cmd) points at `atlas_triage_cli.py`, NOT `atlas.py`. `atlas.py` has no `.cmd` shim and nothing active invokes it.
- **Recommendation:** KEEP. It's the daily-cycle CLI counterpart to `atl`. Renaming to `atlas_daily.py` + adding a `day.cmd` shim is the only hygiene nit — out of scope for this pass.

---

## 4. CycleBoard minimum-change list

One payload file, one CLI command, one HTML panel.

**New payload file:** `services/cognitive-sensor/cycleboard/brain/lifecycle_board.json`
```json
{
  "generated_at": "2026-04-21T15:00:00Z",
  "in_progress": [
    {"convo_id":"...", "title":"...", "status":"BUILDING",
     "artifact_path":"apps/...", "building_started_at":"..."}
  ],
  "terminal_today": {
    "DONE":    [{"loop_id":"487","title":"Marketing for Beginners",
                 "artifact_path":"apps/ai-exec-pipeline","coverage_score":0.186}],
    "RESOLVED":[],
    "DROPPED": []
  },
  "counts": {"HARVESTED":0,"PLANNED":0,"BUILDING":1,"REVIEWING":0,
             "DONE":1,"RESOLVED":0,"DROPPED":0}
}
```
Source: scan `harvest/*/manifest.json` for non-terminal statuses, join with today's `closures.json` entries.

**New `cycleboard/cli.ts` command:** `cycleboard lifecycle` — renders the three sections (in-progress, terminal-today, counts) as a time-block-style panel from the new JSON.

**New HTML panel sketch (index.html):**
```
+-- Lifecycle --------------------------------------------+
| In progress                                             |
|  [BUILDING]   487  Marketing for Beginners              |
|                    -> apps/ai-exec-pipeline  (5h)       |
| Finished today                                          |
|  [DONE]       487  cov 0.19  apps/ai-exec-pipeline      |
|  [RESOLVED]   -                                         |
|  [DROPPED]    -                                         |
| Counts  H:0 P:0 B:1 R:0 / D:1 Rs:0 Dp:0                 |
+---------------------------------------------------------+
```

---

## 5. Worked example

### `atlas-ai auto-archive-stale` on a stale thread 555 today

**Is today:**
- POST `{loop_id:"555", outcome:"archived", title:"atlas-ai auto-archive (stale)"}`
- closureEntry persisted: `{ts, loop_id:"555", title:"atlas-ai auto-archive (stale)", outcome:"archived", artifact_path:null, coverage_score:null, status:null}`
- **No manifest check.** Will archive a thread even if its manifest says `BUILDING`. Silent overwrite risk.

**Should be:**
- Pre-check: read `harvest/555_*/manifest.json`; if `status ∈ {PLANNED, BUILDING, REVIEWING}`, skip and log `"skipped mid-lifecycle"`.
- Payload: `{loop_id:"555", outcome:"archived", title:"...", status:"DROPPED", artifact_path:null, coverage_score:null}`.

### `python close_loop.py 555 ARCHIVE` today

**Is today (close_loop.py:234):**
- INSERT into `loop_decisions` (convo_id=555, decision=ARCHIVE).
- POST `{loop_id:555, title, outcome:"archived"}`.
- `refresh_pipeline()` runs; 555 stops showing in `loops_latest.json`.
- closureEntry lacks `artifact_path / coverage_score / status`.

**Should be:**
- Same DB + refresh side effects.
- Payload: `{..., artifact_path:null, coverage_score:null, status:"DROPPED"}`.

---

## Summary

- 6 legacy POST sites still emit the old 3-field payload (close_loop.py plus five TS call sites in atlas-ai.ts / atlas.ts). `atl` is the only correct writer.
- 9 reader files are blind — none consume `artifact_path`, `coverage_score`, `status`, or mid-lifecycle states. `closures.json` is not even wired into CycleBoard's brain.
- `atlas.py` is not a duplicate of `atl` — it is the daily routing engine. Keep.
- Minimum CycleBoard change: `lifecycle_board.json` emitted by `wire_cycleboard.py`, one `cycleboard lifecycle` command in `cli.ts`, one Lifecycle panel in `index.html`.
