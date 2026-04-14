# Schedule Pre Atlas Services to Start on Login
# Run this script once (as admin) to register all 3 service tasks.
# Services will auto-start when you log into Windows.

$ScriptDir = "C:\Users\bruke\Pre Atlas\scripts"

$services = @(
    @{
        TaskName = "PreAtlas-DeltaKernel"
        Script   = "$ScriptDir\svc_delta_kernel.ps1"
        Desc     = "Pre Atlas: Delta-Kernel API on port 3001"
    },
    @{
        TaskName = "PreAtlas-OpenClaw"
        Script   = "$ScriptDir\svc_openclaw.ps1"
        Desc     = "Pre Atlas: OpenClaw messaging gateway on port 3004"
    },
    @{
        TaskName = "PreAtlas-Orchestrator"
        Script   = "$ScriptDir\svc_orchestrator.ps1"
        Desc     = "Pre Atlas: Mosaic Orchestrator on port 3005"
    }
)

foreach ($svc in $services) {
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$($svc.Script)`""

    $trigger = New-ScheduledTaskTrigger -AtLogOn

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -RestartCount 3 `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0)

    Register-ScheduledTask `
        -TaskName $svc.TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description $svc.Desc `
        -Force

    Write-Host "Registered: $($svc.TaskName)" -ForegroundColor Green
}

Write-Host ""
Write-Host "All 3 services registered for auto-start on login." -ForegroundColor Cyan
Write-Host ""
Write-Host "Services will start automatically when you log in."
Write-Host "To start them NOW, run: .\scripts\start_all_services.ps1"
Write-Host ""
Write-Host "Verify with: Get-ScheduledTask -TaskName 'PreAtlas-*'" -ForegroundColor DarkGray
