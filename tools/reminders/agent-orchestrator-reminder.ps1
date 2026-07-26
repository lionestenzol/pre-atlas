# Reminder: build tools/agent-orchestrator/ (thin Python dispatcher).
#
# Logic:
#   - If C:\Users\bruke\Pre Atlas\tools\agent-orchestrator\ exists -> built!
#     Unregister the scheduled task so it stops firing. Exit silently.
#   - Otherwise -> show a Windows balloon notification.
#
# Background — see:
#   ~/.claude/projects/C--Users-bruke-Pre-Atlas/memory/feedback_agent_orchestration_token_budget.md
#
# Manual disable (any time):
#   Unregister-ScheduledTask -TaskName "PreAtlas-AgentOrchestratorReminder" -Confirm:$false

$ErrorActionPreference = 'SilentlyContinue'

$ProjectRoot = 'C:\Users\bruke\Pre Atlas'
$Target = Join-Path $ProjectRoot 'tools\agent-orchestrator'
$TaskName = 'PreAtlas-AgentOrchestratorReminder'
$LogFile = Join-Path $ProjectRoot 'tools\reminders\reminder.log'

function Write-Log($msg) {
    try {
        "$((Get-Date).ToString('o')) $msg" | Add-Content -Path $LogFile -Encoding utf8
    } catch {}
}

if (Test-Path -LiteralPath $Target) {
    Write-Log "BUILT — unregistering scheduled task."
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    } catch {
        Write-Log "Unregister failed: $($_.Exception.Message)"
    }
    exit 0
}

# Not built — fire a balloon notification.
try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    $balloon = New-Object System.Windows.Forms.NotifyIcon
    $balloon.Icon = [System.Drawing.SystemIcons]::Information
    $balloon.BalloonTipTitle = 'Build the agent orchestrator'
    $balloon.BalloonTipText  = 'Pre Atlas tools/agent-orchestrator/ still missing. Memory: feedback_agent_orchestration_token_budget.md'
    $balloon.Visible = $true
    $balloon.ShowBalloonTip(10000)
    Start-Sleep -Seconds 11
    $balloon.Dispose()
    Write-Log "FIRED — balloon shown."
} catch {
    Write-Log "Notification failed: $($_.Exception.Message)"
}
