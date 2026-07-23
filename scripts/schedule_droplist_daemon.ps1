# Schedule the DropList self-advancing daemon (Brick 3 — cron/temporal control).
# Registers a Windows Task Scheduler entry that runs `droplist.daemon --once`
# on a fixed interval (default 5 min), making DropList a self-advancing entity
# WITHOUT an always-on process. The task fires at logon AND every -IntervalMinutes.
#
# Usage:
#   .\scripts\schedule_droplist_daemon.ps1                 # 5-minute cadence
#   .\scripts\schedule_droplist_daemon.ps1 -IntervalMinutes 15
# Unschedule:
#   .\scripts\unschedule_droplist_daemon.ps1
#
# WHY Task Scheduler (assemble-first, ~/.claude/rules/common/assemble-first.md):
# the repo already schedules every periodic job through Windows Task Scheduler
# (schedule_governor.ps1, install_atlas_autostart.ps1). It is the mature,
# OS-native cron here — no extra Python process to keep alive, self-heals on
# crash, survives reboot. APScheduler/croniter would add a long-lived process
# that competes with the existing DROPLIST_DAEMON=1 in-process thread (Brick 2):
# worse, not just later.

param(
    [int]$IntervalMinutes = 5
)

$ErrorActionPreference = "Stop"
$TaskName   = "PreAtlas-DropList-Daemon"
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $RepoRoot "scripts\run_droplist_daemon.ps1"
$WorkingDir = Join-Path $RepoRoot "services\droplist"

if ($IntervalMinutes -lt 1) {
    throw "IntervalMinutes must be >= 1 (got $IntervalMinutes)"
}

Write-Host ""
Write-Host "Scheduling DropList daemon (every $IntervalMinutes min)..." -ForegroundColor Cyan

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ + $ScriptPath + """") `
    -WorkingDirectory $WorkingDir

# Two triggers: fire at logon AND every N minutes. run_droplist_daemon.ps1 is
# idempotent (--once reads the clock fresh, per-day recurrence, append-only
# audit), so repeat firings only advance whatever is now runnable.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$repeatTrigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($logonTrigger, $repeatTrigger) `
    -Settings $settings `
    -Description "DropList self-advancing daemon: droplist.daemon --once every $IntervalMinutes min (materialize recurring + advance runnable DAGs)" `
    -RunLevel Limited | Out-Null

Write-Host "  [OK] Scheduled task registered: $TaskName" -ForegroundColor Green
Write-Host ""
Write-Host "  DropList will self-advance every $IntervalMinutes minutes (and at logon)." -ForegroundColor White
Write-Host "  Log: $WorkingDir\daemon_cron.log" -ForegroundColor DarkGray
Write-Host ""
Write-Host ("  Run now:    Start-ScheduledTask -TaskName " + $TaskName) -ForegroundColor DarkGray
Write-Host ("  Verify:     Get-ScheduledTask -TaskName " + $TaskName) -ForegroundColor DarkGray
Write-Host "  Unschedule: .\scripts\unschedule_droplist_daemon.ps1" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  NOTE: pick ONE cron arm OR the in-process DROPLIST_DAEMON=1 thread," -ForegroundColor Yellow
Write-Host "        not both — they run the same _run_once() loop." -ForegroundColor Yellow
Write-Host ""
