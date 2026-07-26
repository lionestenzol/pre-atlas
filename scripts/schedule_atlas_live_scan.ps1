# schedule_atlas_live_scan.ps1
# Registers a Windows Scheduled Task that runs scan_atlas_live.ps1 every 15 minutes.
# Run this once (elevated NOT required - RunLevel Limited) to install the schedule.
# This is the "self-updating" wiring for the live surface inventory.
# Companion of schedule_atlas_map_refresh.ps1 (daily manifest regen at 05:00) -
# together they keep both the STRUCTURAL and LIVENESS views of Atlas fresh.

$TaskName   = "AtlasLiveScan"
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $RepoRoot "scripts\scan_atlas_live.ps1"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`"" `
    -WorkingDirectory $RepoRoot

# Every 15 minutes, indefinitely. StartBoundary = now-ish so the first tick fires
# within 15 min of registration; RepetitionInterval + RepetitionDuration span the day.
$startAt = (Get-Date).AddMinutes(1)
$Trigger = New-ScheduledTaskTrigger -Once -At $startAt `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Atlas - every-15-min liveness scan (surfaces UP/DOWN/CONFLICT + HTML inventory + atlas-map reload)" `
    -RunLevel Limited | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered." -ForegroundColor Green
Write-Host "  Trigger:  every 15 minutes, first at $($startAt.ToString('HH:mm'))"
Write-Host "  Action:   $ScriptPath"
Write-Host "  Outputs:  audit\atlas_live.json, audit\atlas_live.md"
Write-Host ""
Write-Host "Verify:   Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Test run: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove:   Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
