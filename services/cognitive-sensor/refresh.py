"""
Master refresh script for the Cognitive Operating System.
Runs the full analysis pipeline in sequence with retry logic.

Can be run from any directory - uses script location as base.
Uses a file-based process lock to prevent concurrent pipeline runs.
"""
from pathlib import Path
import subprocess
import sys
import time
import os
import atexit

BASE = Path(__file__).parent.resolve()
LOCK_FILE = BASE / ".pipeline.lock"

MAX_RETRIES = 2
RETRY_DELAY_S = 3
# If lock is older than 2x expected max runtime (30 min), consider it stale
STALE_LOCK_S = 1800

results: list[tuple[str, str]] = []


def acquire_lock() -> None:
    """Acquire exclusive pipeline lock. Exits if another run is active."""
    if LOCK_FILE.exists():
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            lock_pid = int(LOCK_FILE.read_text().strip().split("\n")[0])
        except (ValueError, OSError):
            lock_age = 0
            lock_pid = -1

        # Check if stale (process dead or lock too old)
        pid_alive = False
        try:
            os.kill(lock_pid, 0)
            pid_alive = True
        except (OSError, ProcessLookupError):
            pid_alive = False

        if pid_alive and lock_age < STALE_LOCK_S:
            print(f"[LOCK] Pipeline already running (PID {lock_pid}, age {lock_age:.0f}s). Exiting.")
            sys.exit(0)
        else:
            reason = "stale lock" if lock_age >= STALE_LOCK_S else f"PID {lock_pid} dead"
            print(f"[LOCK] Removing {reason}, taking over.")

    LOCK_FILE.write_text(f"{os.getpid()}\n{time.time()}\n")
    atexit.register(release_lock)


def release_lock() -> None:
    """Release the pipeline lock."""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def run(script: str) -> None:
    """Run a script with retry logic. Skips missing scripts, retries on failure."""
    script_path = BASE / script
    if not script_path.exists():
        print(f"  [SKIP] {script} not found")
        results.append((script, "skipped"))
        return

    for attempt in range(MAX_RETRIES + 1):
        try:
            subprocess.check_call([sys.executable, script], cwd=BASE)
            results.append((script, "ok"))
            return
        except subprocess.CalledProcessError as e:
            if attempt < MAX_RETRIES:
                print(f"  [RETRY] {script} failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), retrying in {RETRY_DELAY_S}s...")
                time.sleep(RETRY_DELAY_S)
            else:
                print(f"  [FAIL] {script} failed after {MAX_RETRIES + 1} attempts (exit code {e.returncode})")
                results.append((script, "failed"))


# === PROCESS LOCK ===
acquire_lock()

run("behavioral_memory_assess.py")
run("governance_config_api.py")
run("loops.py")
run("completion_stats.py")
run("export_cognitive_state.py")
run("run_graph_ingest.py")
run("route_today.py")
run("run_predictions.py")
run("export_daily_payload.py")
run("wire_cycleboard.py")
run("behavioral_memory_snapshot.py")
run("drift_detector.py")
run("reporter.py")
run("build_dashboard.py")
run("build_strategic_priorities.py")
run("genesis_tree.py")
run("ghost_executor.py")
run("build_docs_manifest.py")

# Summary
failed = [s for s, status in results if status == "failed"]
skipped = [s for s, status in results if status == "skipped"]
ok_count = sum(1 for _, status in results if status == "ok")

if failed:
    print(f"\nRefreshed with errors: {ok_count} ok, {len(failed)} failed ({', '.join(failed)}), {len(skipped)} skipped")
else:
    print(f"\nRefreshed. {ok_count} scripts completed, {len(skipped)} skipped.")
