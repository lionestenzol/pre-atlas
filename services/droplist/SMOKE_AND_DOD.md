# DropList Lifecycle Spine — Definition of Done + Smoke / Break Plan

Covers bricks 1–4 (commits `e44b3a4`, `fe03142`) as ONE system: the project
lifecycle **capture → plan → schedule → advance → check-in → act → track**.

This is the contract we test against. Three parts:
- **§A Definition of Done** — observable, system-level acceptance (not unit tests).
- **§B Smoke tests** — happy-path, copy-pasteable, with expected results.
- **§C Break tests** — adversarial; the bar is *fail-loud, never crash/corrupt*.
- **§D Known gaps** — explicitly out of scope for "done"; this is the backlog.
- **§E Pass gate** — what "solid" means before we move on.

Real surface (verified against committed code):

| Action | How |
|--------|-----|
| Boot API | `cd services/droplist && python -m uvicorn droplist.server:app --port 3073` (or launch config `droplist`) |
| Capture | `POST /api/drop` `{"raw":"..."}` |
| Plan view | `GET /api/dag/{id}/checklist` (server.py:313) |
| Mark off | `POST /api/dag/{id}/node/{node_id}/complete` (server.py:242) · body optional `{"result","evidence","note"}` |
| Reopen | `POST /api/dag/{id}/node/{node_id}/reopen` (server.py:338) |
| Track | `GET /api/brief` (server.py:185), `GET /api/dags` (server.py:133) |
| Headless tick | `python -m droplist.daemon --once` (daemon.py:156) · loop: `--interval N` |
| In-process daemon | env `DROPLIST_DAEMON=1` on the server |
| Chains | `droplist/chain_runner.py` · `tick(now)` (cr.py:504), `run_chain(...)` (cr.py:420), `validate_chain` (cr.py:101) · protocol `chains/*.json` |

> All write endpoints are currently **open** (no token), matching `/api/drop`. The
> break tests below treat that as a known posture, not a failure (see §D).

---

## §A — Definition of Done (system-level, observable)

**Brick 1 — Capture → Plan → Mark-off**
- [ ] A drop becomes a DAG visible via `GET /api/dags`, and its `/checklist`
      lists every task with `status`, `done_condition`, `depends_on`, `blocked_by`.
- [ ] Completing a `ready` node returns the freshly `ready_now` set; a dependent
      that was `waiting` appears in it **only after** its deps are done.
- [ ] Completing the last node flips `dag_status` to `complete`, and `/api/brief`
      shows 0 ready for that DAG.
- [ ] The change is durable: re-`GET` after restart shows the node `done` with the
      submitted `result`/`evidence`.

**Brick 2 — Headless tick (living entity)**
- [ ] `python -m droplist.daemon --once` runs with no server, no input, exit 0,
      and prints a report (materialized / advanced / stale / escalations).
- [ ] Across simulated days (`DROPLIST_NOW`), recurring nodes materialize exactly
      once per due day; stale `ready` nodes (past `stale_after_hours`) get flagged.
- [ ] A `watch_tick` audit record lands in `dag_events.jsonl` each run.
- [ ] Server with `DROPLIST_DAEMON=1` spawns a live daemon thread; without it, none.

**Brick 3 — Cron / temporal control**
- [ ] `scheduler.due_jobs(schedules, now, last_run)` returns the correct due ids at
      a given instant and **excludes** ones already run in the current window.
- [ ] `python -m droplist.daemon --once` is invokable by Windows Task Scheduler via
      `scripts/schedule_droplist_daemon.ps1` (installs), `unschedule_…ps1` (removes).
- [ ] Invalid cron expr is rejected loudly (`ValueError`), not silently ignored.

**Brick 4 — Daisy-chain (staged prompts → report → action)**
- [ ] A chain whose trigger fires runs its step prompts (via `llm.py` heuristic, no
      API key), writes a report record to `chain_reports.jsonl`.
- [ ] The `on_report.action` **changes real state**: `drop` creates a new packet,
      `complete_node` flips a node done + wakes dependents, `emit_signal` emits.
- [ ] A chain whose trigger does **not** fire (wrong time / unmatched condition)
      takes **no** action and writes no spurious report.
- [ ] `validate_chain` rejects a malformed chain (bad `trigger.on`, bad cron,
      condition expr not a dict, bad `on_report.action`) before it can run.
- [ ] `daemon._run_once` runs due chains fail-soft (a broken chain logs, never
      kills the tick).

---

## §B — Smoke tests (happy path)

> Run from `services/droplist`. Use a scratch data dir so smoke never pollutes
> real state: `export DROPLIST_DATA=$(mktemp -d)` (bash) before booting.

**S0 — unit baseline**
```
python -m pytest -q          # expect: 62 passed
```

**S1 — capture → plan → mark-off (live API)**
```
# boot in one terminal:
DROPLIST_DATA=/tmp/dl-smoke python -m uvicorn droplist.server:app --port 3073
# in another:
curl -s -XPOST localhost:3073/api/drop -H 'content-type: application/json' \
  -d '{"raw":"ship the lattice export button: design, build, test"}'
DAG=$(curl -s localhost:3073/api/dags | python -c "import sys,json;print(json.load(sys.stdin)[0]['dag_id'])")
curl -s localhost:3073/api/dag/$DAG/checklist            # expect: tasks[] w/ statuses, blocked_by
N=$(curl -s localhost:3073/api/dag/$DAG/checklist | python -c "import sys,json;print([t['id'] for t in json.load(sys.stdin)['tasks'] if t['status']=='ready'][0]")
curl -s -XPOST localhost:3073/api/dag/$DAG/node/$N/complete \
  -d '{"note":"smoke","evidence":["smoke"]}'             # expect: dag_status, ready_now[] grows
```
PASS: checklist renders; completing the ready node wakes its dependent into
`ready_now`; repeating to the last node yields `dag_status:"complete"`.

**S2 — headless tick**
```
DROPLIST_DATA=/tmp/dl-smoke python -m droplist.daemon --once   # expect: exit 0 + report
```
PASS: prints materialized/advanced/stale counts; a `watch_tick` row appended to
`/tmp/dl-smoke/dag_events.jsonl`.

**S3 — scheduler due-selection**
```
python -c "import droplist.scheduler as s, datetime as d; \
print(s.due_jobs([{'id':'m','cron':'0 8 * * *','action':{'kind':'tick'}}], \
d.datetime(2026,6,25,8,0,0), {}))"                       # expect: ['m']
```
PASS: due at 08:00, and `[]` when last_run already covers the window.

**S4 — chain report → action (the headline)**
```
python -c "import droplist.chain_runner as c, datetime as d; \
print(c.tick(d.datetime(2026,6,25,8,0,0)))"              # expect: chains_fired + actions
```
PASS: with a seeded matching DAG, a follow-up packet/node now exists that didn't
before; `chain_reports.jsonl` has a record. (test_chains.py is the formal proof.)

---

## §C — Break tests (try to break it — expect fail-loud, never crash/corrupt)

| # | Attack | Expected (PASS = graceful) |
|---|--------|----------------------------|
| B1 | `POST .../node/N9/complete` on a non-existent node | `404`, no state change |
| B2 | complete a node whose deps are still open | `409`, message names the blocking dep |
| B3 | complete the **same** node twice | 2nd returns `already_done:true`, `updates:[]` — no double-mutation |
| B4 | `GET /api/dag/NOPE/checklist` | `404`, not 500 |
| B5 | `POST /api/drop` with `{}` / 1-char raw | rejected (min-chars), clear error, no empty DAG |
| B6 | reopen a node in `do_not_reopen` lock | `409` (⚠️ see §D — currently untested path) |
| B7 | malformed chain JSON (bad `trigger.on`) | `validate_chain` raises `ValueError`; loader skips/refuses, tick survives |
| B8 | chain with bad cron expr `"0 99 * * *"` | rejected at validate, never scheduled |
| B9 | chain whose condition matches nothing | no action, no report, tick exit 0 |
| B10 | `daemon --once` with empty/no data dir | exit 0, empty report, creates dirs, no crash |
| B11 | two concurrent `complete` on the same ready node | one wins; no duplicate dependent-wake / corrupt DAG json |
| B12 | giant/garbage body on `complete` | parsed-or-ignored, never 500 |
| B13 | `emit_signal` action with `DROPLIST_ATLAS_SIGNALS_URL` unreachable | fail-soft (retry-buffer/log), tick not killed |

Each Bn that 500s, corrupts a DAG json, hangs, or silently swallows = a real bug
to fix before "done."

---

## §D — Known gaps

**CLOSED 2026-06-25 (commit `8e702e8`, suite 65):**
1. ~~Scheduler half-wired~~ → **wired** into `daemon._run_once`; due `schedules.json`
   entries fire + dedup via `schedule_runs.jsonl` (test_daemon).
2. ~~Reopen lock untested~~ → **tested** (`do_not_reopen` 409 branch).
3. ~~Reopen reimplements derivation~~ → **shared** `dag_update.recompute_states` is now the
   single source of truth for both `apply_review` and reopen.

**Still open (hardening/posture — deliberate backlog, not inert-code bugs):**
4. **Naive-UTC scheduler** — no DST/timezone handling or test.
5. **Open writes** — no auth on the write endpoints (per-spec, local single-user).

---

## §E — Pass gate ("solid", ready to move on)

- [ ] §B S0–S4 all green
- [ ] §C B1–B13 all behave (fail-loud, no 500/corruption/hang)
- [ ] §A boxes checked for bricks 1–4
- [ ] Any bug found in §C is fixed inline (code = furniture) **or** logged in §D with
      a date + owner — never left silently broken.

When §E holds, the spine is smoke-solid and we move to: wiring gap #1, then the
live walkthrough, then hardening (auth, timezone) as warranted.

---

## Run log

**2026-06-25 — first full run.** In-process TestClient harness on a scratch data dir.
- §B smoke S1–S4 + §C break B1–B12: **14/14** after fixes. (B6 do_not_reopen lock, B10
  empty-dir, B13 emit-failsoft: not auto-exercised this run — B6 still untested per §D.)
- **2 real bugs found by break-testing, fixed inline (commit `08b5719`), suite 63 passed:**
  1. Chains fired their `on_report` action on ZERO matching targets (spurious noise drops) —
     `run_chain` never consulted its own step-gate / target list. Gated + regression test.
  2. `daily_ready_nudge` was wired-but-inert via the daemon — `_run_once` advanced ready nodes
     to done before running chains. Reordered: chains before advance.
- Still open from §D: scheduler `due_jobs`/`mark_run` not wired into the daemon; B6 reopen-lock
  untested; reopen reimplements complete-derivation; naive-UTC scheduler; open writes.
