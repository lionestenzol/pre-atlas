"""ingest.py — full corpus refresh: ChatGPT exports -> fully-baked triage cards.

Run this when new ChatGPT exports have landed and you want every downstream
artifact (results.db, embeddings, atlas clusters, ideas, thread cards,
governor brief, dashboard) regenerated against the new corpus.

The pipeline is staged so each step has a known cost. The slow steps
(embeddings, atlas) can be skipped with --fast; partial reruns are supported
via --from <stage>.

Stages (in order):

    corpus      build_memory_db.py            ~1-2 min  fast
    titles      init_titles.py                ~5 sec    fast
    convo_time  init_convo_time.py            ~2 sec    fast
    messages    init_results_db.py            ~1 min    fast
    topics      init_topics.py                ~10 sec   fast
    embeddings  init_message_embeddings.py    ~45-75 min  SLOW (--fast skips)
    atlas       build_cognitive_atlas.py      ~10 min   slow (--fast skips)
    mining      run_agents.py                 ~5-10 min medium
    audit       run_audit.py                  ~3-5 min  medium
    daily       run_daily.py                  ~2-3 min  medium

Usage:
    python ingest.py                       # full rebuild
    python ingest.py --fast                # skip embeddings + atlas (use existing)
    python ingest.py --from atlas          # resume from a specific stage
    python ingest.py --only corpus titles  # run a subset
    python ingest.py --list                # show stages and exit
    python ingest.py --dry-run             # show what would run, do nothing
    python ingest.py --no-backup           # don't back up existing memory_db.json

Per-stage log lands in ingest_log.json so the next run can show "last run:
embeddings OK at 03:42, atlas FAILED" and you can resume with --from atlas.

Uses the same .pipeline.lock as refresh.py so they don't stomp each other.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).parent.resolve()
LOCK_FILE = BASE / ".pipeline.lock"
LOG_FILE = BASE / "ingest_log.json"

STALE_LOCK_S = 60 * 60 * 3  # 3 hr — full ingest can take ~90 min, give 2× headroom


@dataclass(frozen=True)
class Stage:
    name: str
    script: str
    cost: str  # "fast" | "medium" | "slow"
    estimate: str
    description: str


STAGES: tuple[Stage, ...] = (
    Stage("corpus", "build_memory_db.py", "fast", "~1-2 min",
          "merge ChatGPT exports -> memory_db.json + conversations.json"),
    Stage("titles", "init_titles.py", "fast", "~5 sec",
          "populate convo_titles table"),
    Stage("convo_time", "init_convo_time.py", "fast", "~2 sec",
          "populate convo_time table"),
    Stage("messages", "init_results_db.py", "fast", "~1 min",
          "populate messages table"),
    Stage("topics", "init_topics.py", "fast", "~10 sec",
          "populate topics table"),
    Stage("embeddings", "init_message_embeddings.py", "slow", "~45-75 min",
          "sentence-transformers re-embed of all messages"),
    Stage("atlas", "build_cognitive_atlas.py", "slow", "~10 min",
          "UMAP+HDBSCAN -> atlas_clusters.json + cognitive_atlas.html"),
    Stage("mining", "run_agents.py", "medium", "~5-10 min",
          "excavator -> deduplicator -> classifier -> orchestrator -> reporter"),
    Stage("audit", "run_audit.py", "medium", "~3-5 min",
          "classifier_convo -> synthesizer (BEHAVIORAL_AUDIT.md)"),
    Stage("daily", "run_daily.py", "medium", "~2-3 min",
          "loops + governor + cycleboard + dashboard"),
)

STAGE_BY_NAME = {s.name: s for s in STAGES}


# --- lock (shared with refresh.py) ---

def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            lock_pid = int(LOCK_FILE.read_text().strip().split("\n")[0])
        except (ValueError, OSError):
            lock_age = 0
            lock_pid = -1
        pid_alive = False
        try:
            os.kill(lock_pid, 0)
            pid_alive = True
        except (OSError, ProcessLookupError):
            pid_alive = False
        if pid_alive and lock_age < STALE_LOCK_S:
            print(f"[LOCK] Pipeline already running (PID {lock_pid}, age {lock_age:.0f}s). Exiting.")
            sys.exit(0)
        print(f"[LOCK] Removing {'stale lock' if lock_age >= STALE_LOCK_S else f'dead PID {lock_pid}'}, taking over.")
    LOCK_FILE.write_text(f"{os.getpid()}\n{time.time()}\n")
    atexit.register(release_lock)


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# --- log ---

def load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"runs": []}


def save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")


# --- stage planning ---

def select_stages(
    only: list[str] | None,
    from_stage: str | None,
    fast: bool,
) -> list[Stage]:
    """Pick which stages to run, honoring --only, --from, and --fast."""
    if only:
        unknown = set(only) - STAGE_BY_NAME.keys()
        if unknown:
            sys.exit(f"unknown stage(s): {sorted(unknown)}. valid: {[s.name for s in STAGES]}")
        return [STAGE_BY_NAME[n] for n in only]

    selected = list(STAGES)
    if from_stage:
        if from_stage not in STAGE_BY_NAME:
            sys.exit(f"unknown --from stage: {from_stage}. valid: {[s.name for s in STAGES]}")
        start = next(i for i, s in enumerate(STAGES) if s.name == from_stage)
        selected = list(STAGES[start:])

    if fast:
        selected = [s for s in selected if s.cost != "slow"]

    return selected


# --- stage runner ---

def run_stage(stage: Stage, extra_args: list[str], dry_run: bool) -> dict:
    """Run one stage. Returns a log entry. Re-raises on failure."""
    script_path = BASE / stage.script
    cmd = [sys.executable, "-u", str(script_path), *extra_args]
    header = f"[{stage.name}] {stage.script} ({stage.estimate}) - {stage.description}"
    print(f"\n{'-' * 70}\n{header}\n{'-' * 70}")

    if dry_run:
        print(f"  [DRY] would run: {' '.join(cmd)}")
        return {"stage": stage.name, "status": "dry-run", "duration_s": 0}

    if not script_path.exists():
        print(f"  [SKIP] {stage.script} not found")
        return {"stage": stage.name, "status": "skipped", "duration_s": 0}

    start = time.time()
    try:
        subprocess.check_call(cmd, cwd=BASE)
        elapsed = time.time() - start
        print(f"  [OK] {stage.name} in {elapsed:.1f}s")
        return {
            "stage": stage.name,
            "status": "ok",
            "duration_s": round(elapsed, 1),
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start
        print(f"  [FAIL] {stage.name} after {elapsed:.1f}s (exit {e.returncode})")
        print(f"  Resume from this stage with:  python ingest.py --from {stage.name}")
        return {
            "stage": stage.name,
            "status": "failed",
            "duration_s": round(elapsed, 1),
            "returncode": e.returncode,
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


# --- cli ---

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--fast", action="store_true",
                   help="skip slow stages (embeddings, atlas) — use existing artifacts")
    p.add_argument("--from", dest="from_stage", metavar="STAGE",
                   help="resume pipeline from this stage onward")
    p.add_argument("--only", nargs="+", metavar="STAGE",
                   help="run only these stages (overrides --from / --fast)")
    p.add_argument("--list", action="store_true", help="list stages and exit")
    p.add_argument("--dry-run", action="store_true", help="show what would run, do nothing")
    p.add_argument("--no-backup", action="store_true",
                   help="pass --no-backup through to build_memory_db.py")
    p.add_argument("--continue-on-fail", action="store_true",
                   help="keep running later stages after a failure (default: stop)")
    args = p.parse_args()

    if args.list:
        print(f"{'STAGE':<12} {'COST':<8} {'EST':<12} SCRIPT")
        print("-" * 70)
        for s in STAGES:
            print(f"{s.name:<12} {s.cost:<8} {s.estimate:<12} {s.script}")
        return 0

    selected = select_stages(args.only, args.from_stage, args.fast)
    if not selected:
        print("No stages selected. Try --list.")
        return 1

    print("=" * 70)
    print(f"INGEST - {len(selected)} stage(s)")
    for s in selected:
        print(f"  * {s.name:<12} ({s.cost:<6}, {s.estimate})")
    print("=" * 70)

    if not args.dry_run:
        acquire_lock()

    # Per-stage extra args (only build_memory_db gets --no-backup)
    extras_by_stage: dict[str, list[str]] = {
        "corpus": ["--no-backup"] if args.no_backup else [],
    }

    run_entries: list[dict] = []
    total_start = time.time()
    failed_stage: str | None = None

    for stage in selected:
        entry = run_stage(stage, extras_by_stage.get(stage.name, []), args.dry_run)
        run_entries.append(entry)
        if entry["status"] == "failed":
            failed_stage = stage.name
            if not args.continue_on_fail:
                break

    total_elapsed = time.time() - total_start

    # Log this run
    if not args.dry_run:
        log = load_log()
        log["runs"].append({
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(total_start)),
            "duration_s": round(total_elapsed, 1),
            "fast": args.fast,
            "from": args.from_stage,
            "only": args.only,
            "stages": run_entries,
            "ok": failed_stage is None,
        })
        # Keep the last 20 runs
        log["runs"] = log["runs"][-20:]
        save_log(log)

    # Summary
    print(f"\n{'=' * 70}")
    ok_count = sum(1 for e in run_entries if e["status"] == "ok")
    fail_count = sum(1 for e in run_entries if e["status"] == "failed")
    skip_count = sum(1 for e in run_entries if e["status"] == "skipped")
    status = "OK" if failed_stage is None else f"FAILED at {failed_stage}"
    print(f"INGEST {status} - {ok_count} ok, {fail_count} failed, {skip_count} skipped"
          f" - {total_elapsed:.0f}s total")
    print("=" * 70)
    return 0 if failed_stage is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
