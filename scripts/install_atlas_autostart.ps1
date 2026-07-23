# Install Atlas to auto-start on Windows login.
# Registers a Task Scheduler entry that runs start_atlas.ps1 hidden at logon.
# Also creates a Start Menu shortcut and a Desktop shortcut.
# Usage: .\scripts\install_atlas_autostart.ps1
# Uninstall: .\scripts\uninstall_atlas_autostart.ps1

$ErrorActionPreference = "Stop"
$TaskName = "Atlas-Autostart"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $RepoRoot "scripts\start_atlas.ps1"

Write-Host ""
Write-Host "Installing Atlas auto-start..." -ForegroundColor Cyan

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ + $ScriptPath + """")
# Two triggers: fire at logon AND every 15 minutes so dead services self-heal.
# start_atlas.ps1 is idempotent (Get-NetTCPConnection guard skips live services),
# so repeat firings only respawn what's down.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$repeatTrigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 9999)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($logonTrigger, $repeatTrigger) `
    -Settings $settings `
    -Description "Atlas - start standalone services at login + self-heal every 15 min" `
    -RunLevel Limited | Out-Null

Write-Host "  [OK] Scheduled task registered: $TaskName" -ForegroundColor Green

$wsh = New-Object -ComObject WScript.Shell

$startMenu = [Environment]::GetFolderPath('StartMenu')
$shortcutPath = Join-Path $startMenu "Programs\Atlas.lnk"
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments  = ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ + $ScriptPath + """")
$shortcut.WorkingDirectory = $RepoRoot
$shortcut.Description = "Start Atlas and open inPACT"
$shortcut.IconLocation = "powershell.exe,0"
$shortcut.Save()
Write-Host "  [OK] Start Menu shortcut: $shortcutPath" -ForegroundColor Green

$desktop = [Environment]::GetFolderPath('Desktop')
$desktopShortcut = Join-Path $desktop "Atlas.lnk"
$shortcut2 = $wsh.CreateShortcut($desktopShortcut)
$shortcut2.TargetPath = $shortcut.TargetPath
$shortcut2.Arguments  = $shortcut.Arguments
$shortcut2.WorkingDirectory = $shortcut.WorkingDirectory
$shortcut2.Description = $shortcut.Description
$shortcut2.IconLocation = $shortcut.IconLocation
$shortcut2.Save()
Write-Host "  [OK] Desktop shortcut: $desktopShortcut" -ForegroundColor Green

Write-Host ""
Write-Host "DONE." -ForegroundColor Green
Write-Host ""
Write-Host "  Atlas will auto-start every time you log in to Windows." -ForegroundColor White
Write-Host "  Hit Win key, type 'Atlas', press Enter to start manually." -ForegroundColor White
Write-Host "  Or double-click the Atlas icon on your Desktop." -ForegroundColor White
Write-Host ""
Write-Host ("  Start now: Start-ScheduledTask -TaskName " + $TaskName) -ForegroundColor DarkGray
Write-Host "  Uninstall: .\scripts\uninstall_atlas_autostart.ps1" -ForegroundColor DarkGray
Write-Host ""
