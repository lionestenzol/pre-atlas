# AUTO_SHIPPING — The Daily Loop

How Pre Atlas ships work without you pushing a button.

---

## What runs automatically

Two Windows scheduled tasks drive the loop:

1. **`PreAtlas-DailyPipeline`** — fires daily at **06:30**. Runs
   `services/cognitive-sensor/run_daily.py`, which executes the full
   cognitive-sensor pipeline (Phases 1–6). Phase 4.5 calls
   `cycleboard_push.py` — it reads `auto_actor_log.json`, writes unseen
   decisions to the delta-kernel journal, and marks them in the dedup
   ledger.

2. **`PreAtlas-CycleboardRetry`** — fires daily at **06:45**. Runs
   `cycleboard_push.py` standalone. If delta-kernel was down at 06:30,
   this second pass picks up the pending journal entries once the API
   is reachable. Bridge dedup prevents double-posting.

The chain: `run_daily` → `auto_actor` → `cycleboard_push` → delta-kernel
journal → CycleBoard dashboard → (human review) → `atlas_approve` →
`proposal_runner`.

Everything upstream of approval is headless. Approval is deliberately
manual.

---

## What requires you

You review items the auto_actor flagged as `[REVIEW]`. Two paths:

- **CLI** — `python services/cognitive-sensor/atlas_approve.py list`
  shows pending proposals; `atlas_approve.py approve <id>` fires
  `proposal_runner` via `claude -p` and writes the result back.
- **In-session** — `/run-proposal <id>` inside Claude Code runs the
  same proposal without spawning a subprocess. Faster when you're
  already in a session.

Auto-shipped items (`[AUTO]`) don't need you. They're in the archive
if you want to audit.

---

## Where to look

- **CycleBoard journal** — delta-kernel dashboard. Source of truth for
  what auto_actor decided today.
- **`services/cognitive-sensor/proposals.json`** — open proposals
  awaiting approval.
- **`services/cognitive-sensor/auto_actor_log_archive.jsonl`** — every
  auto_actor decision, append-only. Check here when you want history.
- **`services/cognitive-sensor/cycleboard_push_ledger.json`** — bridge
  dedup ledger. Tells you what's been pushed vs. pending.
- **`schtasks //query //tn "PreAtlas*" //fo LIST //v`** — task status
  + next run times.

---

## How to pause

Disable one or both tasks:

```
schtasks //change //tn "PreAtlas-DailyPipeline" //disable
schtasks //change //tn "PreAtlas-CycleboardRetry" //disable
```

Re-enable with `//enable`. Delete entirely with
`schtasks //delete //tn "PreAtlas-DailyPipeline" //f`.

The pipeline also runs fine manually: `python run_daily.py` from
`services/cognitive-sensor/`. The scheduler is a convenience layer,
not a dependency.

---

## How to debug

**Pipeline didn't run overnight:**
- `schtasks //query //tn "PreAtlas-DailyPipeline" //fo LIST //v`
  shows Last Run Time + Last Result. Non-zero result = Python error.
- Run manually to see the traceback:
  `python services/cognitive-sensor/run_daily.py`.

**Pipeline ran but CycleBoard is stale:**
- Check if delta-kernel was up at 06:30. The 06:45 retry should have
  caught it — look at `cycleboard_push_ledger.json` timestamps.
- Run the bridge manually: `python services/cognitive-sensor/cycleboard_push.py`.

**Approval didn't fire:**
- `proposal_runner.py` uses `claude -p` headless. Confirm `claude`
  CLI is on PATH and authenticated.
- Check the proposal's exit status in `proposals.json`.

**Want to replay a day:**
- The archive (`auto_actor_log_archive.jsonl`) has every decision.
  The bridge ledger prevents re-pushing; clear specific entries from
  the ledger to force a re-push.

---

## Why this shape

Two tasks instead of one long-running service: no NSSM install, no
admin rights, no daemon to babysit. If delta-kernel is down, the
retry covers it. If the retry also misses, the next day's run picks
up via dedup. Graceful degradation, zero dependencies.

Approval stays manual on purpose. Auto-shipping a `[REVIEW]` item
would defeat the point of the review flag.
