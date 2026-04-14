# Schedule Governor Tasks in Windows Task Scheduler
# Run this script once (as admin) to register both daily and weekly tasks

$scriptDir = "C:\Users\bruke\Pre Atlas\scripts"

# Daily task: 7:00 AM every day
$dailyAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptDir\run_governor_daily.ps1`"" `
    -WorkingDirectory "C:\Users\bruke\Pre Atlas\services\cognitive-sensor"

$dailyTrigger = New-ScheduledTaskTrigger -Daily -At 7:00AM

$dailySettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName "PreAtlas-Governor-Daily" `
    -Action $dailyAction `
    -Trigger $dailyTrigger `
    -Settings $dailySettings `
    -Description "Pre Atlas daily governor: refresh pipeline + brief generation" `
    -Force

Write-Host "Registered: PreAtlas-Governor-Daily (7:00 AM daily)"

# Weekly task: Sunday 8:00 AM
$weeklyAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptDir\run_governor_weekly.ps1`"" `
    -WorkingDirectory "C:\Users\bruke\Pre Atlas\services\cognitive-sensor"

$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 8:00AM

$weeklySettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName "PreAtlas-Governor-Weekly" `
    -Action $weeklyAction `
    -Trigger $weeklyTrigger `
    -Settings $weeklySettings `
    -Description "Pre Atlas weekly governor: agents + weekly packet" `
    -Force

Write-Host "Registered: PreAtlas-Governor-Weekly (Sunday 8:00 AM)"
Write-Host ""
Write-Host "Done. Verify with: Get-ScheduledTask -TaskName 'PreAtlas-Governor-*'"
