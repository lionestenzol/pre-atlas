# Install atlas-ai agent daemon as a Windows Task Scheduler job.
# Runs on user login, restarts on failure.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install_agent_service.ps1

$ErrorActionPreference = "Stop"
$TaskName = "AtlasAI-Agent-Daemon"
$ScriptPath = Join-Path $PSScriptRoot "start_agent.ps1"
$LogPath = Join-Path $env:USERPROFILE ".atlas\service.log"

# Ensure .atlas dir exists
$atlasDir = Join-Path $env:USERPROFILE ".atlas"
if (-not (Test-Path $atlasDir)) { New-Item -ItemType Directory -Path $atlasDir -Force | Out-Null }

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: run start_agent.ps1 via pwsh
$action = New-ScheduledTaskAction `
    -Execute "pwsh.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`"" `
    -WorkingDirectory (Split-Path $ScriptPath)

# Trigger: at logon
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Settings: restart on failure, don't stop on idle, run indefinitely
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)

# Register
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Atlas AI agent daemon — autonomous governance loop" `
    -RunLevel Limited

Write-Host "[OK] Task '$TaskName' registered. Starts on next login."
Write-Host "     To start now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "     To check:     Get-ScheduledTask -TaskName '$TaskName' | Select State"
Write-Host "     To remove:    Unregister-ScheduledTask -TaskName '$TaskName'"
