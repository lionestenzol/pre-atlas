# schedule_atlas_map_refresh.ps1
# Registers a Windows Scheduled Task that runs refresh_atlas_map.ps1 nightly at
# 05:00 - before the 06:00 AtlasDailyPipeline task (schedule_atlas_daily.ps1) -
# so the map is fresh before the day's push reads from it.
# Run this script once (elevated) to install the schedule.
# Campaign II (LIGHTS_ON, atlas-pivot-AP0001), task 01_switches.

$TaskName = "AtlasMapNightlyRefresh"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $RepoRoot "scripts\refresh_atlas_map.ps1"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`"" `
    -WorkingDirectory $RepoRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At 5:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

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
    -Description "Atlas - nightly system-map regen + atlas-map-api reload" `
    -RunLevel Limited | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered successfully."
Write-Host "  Trigger:  Daily at 05:00 AM"
Write-Host "  Action:   $ScriptPath"
Write-Host ""
Write-Host "Verify with: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Test run:    Start-ScheduledTask -TaskName '$TaskName'"
