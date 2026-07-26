# Remove Atlas auto-start: scheduled task + Start Menu + Desktop shortcuts.
$ErrorActionPreference = "Continue"
$TaskName = "Atlas-Autostart"

Write-Host ""
Write-Host "Uninstalling Atlas auto-start..." -ForegroundColor Cyan

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  [OK] Removed scheduled task: $TaskName" -ForegroundColor Green
} else {
    Write-Host "  [skip] No scheduled task found" -ForegroundColor DarkGray
}

$paths = @(
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) "Programs\Atlas.lnk"),
    (Join-Path ([Environment]::GetFolderPath('Desktop'))  "Atlas.lnk")
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "  [OK] Removed shortcut: $p" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Done. Atlas no longer auto-starts on login." -ForegroundColor Green
Write-Host "(Services that are currently running are NOT stopped — use stop_atlas.bat for that.)"
Write-Host ""
