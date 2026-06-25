# Remove the DropList daemon schedule (Brick 3).
# Unregisters the Windows Task Scheduler entry installed by
# schedule_droplist_daemon.ps1. Does NOT touch the in-process DROPLIST_DAEMON=1
# server thread (that arm is controlled by the env var, not Task Scheduler).

$ErrorActionPreference = "Continue"
$TaskName = "PreAtlas-DropList-Daemon"

Write-Host ""
Write-Host "Unscheduling DropList daemon..." -ForegroundColor Cyan

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  [OK] Removed scheduled task: $TaskName" -ForegroundColor Green
} else {
    Write-Host "  [skip] No scheduled task found" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Done. DropList no longer self-advances on a cron." -ForegroundColor Green
Write-Host "(An in-process DROPLIST_DAEMON=1 server thread, if set, is unaffected.)"
Write-Host ""
