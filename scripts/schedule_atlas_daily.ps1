# schedule_atlas_daily.ps1
# Registers a Windows Scheduled Task that runs the Atlas daily pipeline at 06:00.
# Run this script once (elevated) to install the schedule.

$TaskName = "AtlasDailyPipeline"
$CognitiveSensorDir = Join-Path $PSScriptRoot "..\services\cognitive-sensor"
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = "python" }

$LogDir = Join-Path $CognitiveSensorDir "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "run_daily.py" `
    -WorkingDirectory (Resolve-Path $CognitiveSensorDir).Path

$Trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Remove existing task if present
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
    -Description "Atlas daily governance pipeline — cognitive-sensor run_daily.py" `
    -RunLevel Limited

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered successfully."
Write-Host "  Trigger:  Daily at 06:00 AM"
Write-Host "  Action:   python run_daily.py"
Write-Host "  WorkDir:  $((Resolve-Path $CognitiveSensorDir).Path)"
Write-Host ""
Write-Host "Verify with: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Test run:    Start-ScheduledTask -TaskName '$TaskName'"
