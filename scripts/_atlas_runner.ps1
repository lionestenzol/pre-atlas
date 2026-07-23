# Atlas per-service runner — sets window title, seeds a log header, runs Cmd with tee'd output.
# Reusable helper. Not currently called by start_atlas.ps1 (which inlines its own spawn).
# Manual use:
#   .\scripts\_atlas_runner.ps1 -Name delta -Cwd services\delta-kernel `
#       -LogFile .atlas-logs\delta.log -RunCmd "npm run api"
param(
    [string]$Name,
    [string]$Cwd,
    [string]$LogFile,
    [string]$RunCmd
)
$Host.UI.RawUI.WindowTitle = "atlas-$Name"
Set-Location $Cwd
$header = @(
    "=== atlas: $Name ===",
    "cwd: $Cwd",
    "cmd: $RunCmd",
    "started: $(Get-Date -Format o)",
    ""
) -join "`n"
$header | Out-File -FilePath $LogFile -Encoding utf8
Invoke-Expression "$RunCmd 2>&1" | Tee-Object -FilePath $LogFile -Append
