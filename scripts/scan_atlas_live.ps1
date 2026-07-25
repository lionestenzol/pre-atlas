# scan_atlas_live.ps1 - live liveness + UI inventory over every declared Atlas surface.
#
# Reads .claude/launch.json (the declarative registry, 38+ surfaces) and cross-references
# it against the current TCP listener set + on-disk HTML inventory of each surface's cwd.
# Produces audit/atlas_live.json (machine) + audit/atlas_live.md (human) and, if a write
# token is available, POSTs a reload to atlas-map-api :3072 so the front door reflects
# fresh state without a restart.
#
# This is the self-updating replacement for the hardcoded surface tables in
# status_atlas.ps1 (13 surfaces) and reap_orphans.ps1 (12 surfaces + 2 squatters),
# both of which drifted 25+ surfaces behind launch.json.
#
# Usage:
#   .\scripts\scan_atlas_live.ps1                # scan + write JSON/MD, quiet console
#   .\scripts\scan_atlas_live.ps1 -Verbose       # scan + write + pretty console table
#   .\scripts\scan_atlas_live.ps1 -NoWrite       # scan-only, print to console, don't touch audit/
#   .\scripts\scan_atlas_live.ps1 -NoReload      # skip the atlas-map-api reload POST
#
# Wired to a Windows Scheduled Task by scripts\schedule_atlas_live_scan.ps1.
# See ~/.claude/rules/common/code-as-furniture.md - launch.json is the one source of truth.

param(
    [switch]$Verbose,
    [switch]$NoWrite,
    [switch]$NoReload
)
$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_atlas_manifest.ps1"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AuditDir = Join-Path $RepoRoot "audit"
$OutJson  = Join-Path $AuditDir "atlas_live.json"
$OutMd    = Join-Path $AuditDir "atlas_live.md"

if (-not (Test-Path $AuditDir) -and -not $NoWrite) {
    New-Item -ItemType Directory -Path $AuditDir -Force | Out-Null
}

# Shared manifest / listener helpers - see _atlas_manifest.ps1.
$declared  = Get-AtlasManifest -RepoRoot $RepoRoot
$listeners = Get-TcpListeners

# Cmdline lookup: bulk Win32_Process enumeration cached once.
$procsByPid = @{}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $procsByPid[[int]$_.ProcessId] = $_
}
function Get-Cmdline([int]$Id) { if ($procsByPid.ContainsKey($Id)) { $procsByPid[$Id].CommandLine } else { $null } }
function Get-ExeName([int]$Id) { if ($procsByPid.ContainsKey($Id)) { $procsByPid[$Id].Name } else { $null } }

# --- HTML inventory per surface (bounded scan of each surface's cwd) --------
function Get-HtmlInventory($cwd) {
    if (-not $cwd -or -not (Test-Path $cwd)) { return @() }
    try {
        $files = Get-ChildItem -Path $cwd -Filter '*.html' -Recurse -File -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -notmatch '\\node_modules\\' -and $_.FullName -notmatch '\\dist\\' -and $_.FullName -notmatch '\\\.venv\\' -and $_.FullName -notmatch '\\build\\' } |
                 Select-Object -First 50
        return @($files | ForEach-Object {
            $rel = $_.FullName.Substring($cwd.Length).TrimStart('\','/')
            [pscustomobject]@{ path = $rel; size = $_.Length }
        })
    } catch {
        return @()
    }
}

# --- Cross-reference declared vs live --------------------------------------
$surfaces = @()
$upCount = 0
foreach ($port in ($declared.Keys | Sort-Object)) {
    $d = $declared[$port]
    $status = 'DOWN'
    $pidx = $null
    $cmd  = $null
    $confidence = 'n/a'
    if ($listeners.ContainsKey($port)) {
        $pidx = $listeners[$port]
        $cmd  = Get-Cmdline $pidx
        if ($cmd) {
            if (Test-CmdlineMatches -Cmdline $cmd -Matchers $d.Matchers) { $status = 'UP'; $confidence = 'match'; $upCount++ }
            else { $status = 'CONFLICT'; $confidence = 'wrong-cmdline' }
        } else {
            $status = 'UP'; $confidence = 'unknown-cmd'; $upCount++
        }
    }
    $htmls = Get-HtmlInventory $d.Cwd
    $surfaces += [pscustomobject]@{
        name       = $d.Name
        port       = $port
        status     = $status
        pid        = $pidx
        confidence = $confidence
        cwd        = $d.Cwd
        matcher    = $d.Matcher
        cmdline    = if ($cmd) { ($cmd -replace '\s+', ' ').Substring(0, [Math]::Min(240, ($cmd -replace '\s+', ' ').Length)) } else { $null }
        htmls      = $htmls
        html_count = $htmls.Count
    }
}

# --- Unknown listeners (not in launch.json, not us, not whitelisted) --------
$declaredPorts = @($declared.Keys)
$whitelist     = @(5173)   # noutube-native Electron - see reap_orphans.ps1
$unknown = @()
foreach ($port in ($listeners.Keys | Sort-Object)) {
    if ($declaredPorts -contains $port) { continue }
    if ($whitelist    -contains $port) { continue }
    $pidx = $listeners[$port]
    $cmd  = Get-Cmdline $pidx
    if (-not $cmd) { continue }
    $unknown += [pscustomobject]@{
        port    = $port
        pid     = $pidx
        exe     = Get-ExeName $pidx
        cmdline = ($cmd -replace '\s+', ' ').Substring(0, [Math]::Min(240, ($cmd -replace '\s+', ' ').Length))
    }
}

# --- Emit ------------------------------------------------------------------
$report = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    counts       = @{
        declared = $declared.Count
        up       = $upCount
        down     = ($declared.Count - $upCount - ($surfaces | Where-Object { $_.status -eq 'CONFLICT' }).Count)
        conflict = ($surfaces | Where-Object { $_.status -eq 'CONFLICT' }).Count
        unknown  = $unknown.Count
    }
    surfaces = $surfaces
    unknown  = $unknown
}

if (-not $NoWrite) {
    $report | ConvertTo-Json -Depth 8 | Set-Content -Path $OutJson -Encoding ASCII
    # Markdown summary
    $md = @()
    $md += "# Atlas live scan - $($report.generated_at)"
    $md += ""
    $md += "**Counts:** declared=$($report.counts.declared)  up=$($report.counts.up)  down=$($report.counts.down)  conflict=$($report.counts.conflict)  unknown=$($report.counts.unknown)"
    $md += ""
    $md += "## Surfaces"
    $md += ""
    $md += "| Status | Port | Name | PID | HTMLs | Confidence |"
    $md += "|---|---:|---|---:|---:|---|"
    foreach ($s in ($surfaces | Sort-Object status,port)) {
        $md += "| $($s.status) | $($s.port) | $($s.name) | $($s.pid) | $($s.html_count) | $($s.confidence) |"
    }
    if ($unknown.Count -gt 0) {
        $md += ""
        $md += "## Unknown listeners (not in launch.json, not whitelisted)"
        $md += ""
        $md += "| Port | PID | Exe | Cmdline |"
        $md += "|---:|---:|---|---|"
        foreach ($u in $unknown) {
            $cmdCell = ($u.cmdline -replace '\|','\|')
            $md += "| $($u.port) | $($u.pid) | $($u.exe) | $cmdCell |"
        }
    }
    $md += ""
    $md += "## HTML inventory (up surfaces only)"
    $md += ""
    foreach ($s in ($surfaces | Where-Object { $_.status -eq 'UP' -and $_.html_count -gt 0 } | Sort-Object name)) {
        $md += "### $($s.name)  (:$($s.port))"
        foreach ($h in $s.htmls) { $md += "- ``$($h.path)``" }
        $md += ""
    }
    $md -join "`n" | Set-Content -Path $OutMd -Encoding ASCII
}

# --- Console output --------------------------------------------------------
Write-Host ""
Write-Host "ATLAS live scan" -ForegroundColor Cyan
Write-Host "---------------" -ForegroundColor DarkGray
Write-Host ("  declared={0}  up={1}  down={2}  conflict={3}  unknown={4}" -f $report.counts.declared, $report.counts.up, $report.counts.down, $report.counts.conflict, $report.counts.unknown) -ForegroundColor $(if ($report.counts.conflict -gt 0) {'Yellow'} else {'Green'})
if ($Verbose) {
    Write-Host ""
    foreach ($s in ($surfaces | Sort-Object status,port)) {
        $color = switch ($s.status) { 'UP' {'Green'}; 'DOWN' {'DarkGray'}; 'CONFLICT' {'Yellow'}; default {'White'} }
        Write-Host ("  [{0,-8}] :{1,-5} {2,-24} PID {3,-6} HTMLs {4,-3} {5}" -f $s.status, $s.port, $s.name, ($(if ($s.pid) {$s.pid} else {'-'})), $s.html_count, $s.confidence) -ForegroundColor $color
    }
    if ($unknown.Count -gt 0) {
        Write-Host ""
        Write-Host "  Unknown listeners:" -ForegroundColor Yellow
        foreach ($u in $unknown) {
            Write-Host ("    :{0,-5} PID {1,-6} {2}" -f $u.port, $u.pid, $u.cmdline) -ForegroundColor DarkYellow
        }
    }
}
if (-not $NoWrite) {
    Write-Host ""
    Write-Host "  Wrote $OutJson" -ForegroundColor DarkGray
    Write-Host "  Wrote $OutMd" -ForegroundColor DarkGray
}

# --- Nudge atlas-map-api to reload --------------------------------------------
# Mirrors refresh_atlas_map.ps1's token resolution ladder so a running :3072
# picks up the fresh scan without a service restart.
if (-not $NoReload) {
    $writeToken = $env:ATLAS_WRITE_TOKEN
    if (-not $writeToken) {
        $tokenFile = Join-Path $RepoRoot ".atlas-write-token"
        if (Test-Path $tokenFile) { $writeToken = (Get-Content $tokenFile -Raw).Trim() }
    }
    if ($writeToken) {
        try {
            $null = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3072/admin/reload" -Headers @{ "X-Atlas-Token" = $writeToken } -TimeoutSec 5 -ErrorAction Stop
            Write-Host "  atlas-map-api reloaded" -ForegroundColor DarkGray
        } catch {
            # Silent: :3072 down is a legitimate state we just measured.
        }
    }
}

exit 0
