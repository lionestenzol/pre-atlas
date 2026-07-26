<#
.SYNOPSIS
  One-click DropList launcher (Task D — finishes Bar 1).
  If the server isn't already up on :3073, start it detached, wait for it to
  answer, then open the browser. Double-click a shortcut to this and you get the
  app with zero terminal — the "click-and-invoke" bar.

.NOTES
  Make a desktop shortcut (same pattern as install_atlas_autostart.ps1):
    $W = New-Object -ComObject WScript.Shell
    $lnk = $W.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\DropList.lnk")
    $lnk.TargetPath = "powershell.exe"
    $lnk.Arguments  = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"<repo>\services\droplist\scripts\start_droplist.ps1`""
    $lnk.IconLocation = "<repo>\services\droplist\ui\icons\icon-512.png"
    $lnk.Save()
#>
[CmdletBinding()]
param(
  [int]$Port = 3073
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)  # services/droplist
$Url  = "http://127.0.0.1:$Port/"

function Test-Up {
  try { (Invoke-WebRequest -Uri "$Url`api/now" -TimeoutSec 1 -UseBasicParsing).StatusCode -lt 500 }
  catch { $false }
}

if (-not (Test-Up)) {
  Write-Host "Starting DropList on :$Port ..."
  $env:DROPLIST_PORT = "$Port"
  $env:DROPLIST_DAEMON = "1"
  Start-Process -WindowStyle Hidden -WorkingDirectory $Root `
    -FilePath "python" -ArgumentList @("-m", "droplist.server")
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline -and -not (Test-Up)) { Start-Sleep -Milliseconds 300 }
}

if (Test-Up) { Start-Process $Url } else { Write-Error "DropList did not come up on :$Port" }
