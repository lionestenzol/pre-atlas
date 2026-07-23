# DropList Daemon Runner (Brick 3 — cron/temporal control)
# Called by Windows Task Scheduler on a fixed interval.
# Fires exactly ONE self-advancing tick: `python -m droplist.daemon --once`
#   (watcher.tick materialize+flag, THEN advance every runnable stored DAG).
#
# This is the OS-level scheduler arm. The IN-PROCESS arm is the FastAPI
# DROPLIST_DAEMON=1 startup thread (Brick 2) — pick ONE per box. Both call the
# identical droplist.daemon._run_once(), so there is no second code path to rot
# (~/.claude/rules/common/code-as-furniture.md).
#
# Idempotent + crash-safe: --once reads the DropList clock fresh and appends a
# 'daemon_tick' audit record per pass, so a missed or doubled fire never loses
# or duplicates engine state (storage is append-only / per-day recurrence).

$ErrorActionPreference = "Stop"
$dropDir = "C:\Users\bruke\Pre Atlas\services\droplist"
$logFile = "C:\Users\bruke\Pre Atlas\services\droplist\daemon_cron.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] DropList daemon --once: start" | Out-File -FilePath $logFile -Append

try {
    Set-Location $dropDir
    python -m droplist.daemon --once 2>&1 | Out-File -FilePath $logFile -Append
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] DropList daemon --once: ok" | Out-File -FilePath $logFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $logFile -Append
    exit 1
}
