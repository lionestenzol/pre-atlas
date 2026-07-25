# reap_orphans.ps1 - kill orphaned/duplicate dev servers so a port scan reflects Atlas only.
# Wave 0.3, atlas-consolidation-AC0002. Allow-list derived from .claude/launch.json via
# _atlas_manifest.ps1 (was hardcoded to 12 surfaces; drifted 25+ behind reality). The
# manifest is the single source of truth shared with status_atlas.ps1 and scan_atlas_live.ps1.
# Never touches :5173 (noutube-native, when it's the owner) or any process whose cmdline
# matches any Atlas surface matcher token.
# See ~/.claude/rules/common/code-as-furniture.md - re-detects at run time; PIDs are never hardcoded.
param(
    [switch]$DryRun,
    [switch]$Force   # skip the confirmation prompt (for automation)
)
$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_atlas_manifest.ps1"
$AtlasManifest  = Get-AtlasManifest
$WhitelistPorts = @(5173)   # noutube-native Electron app - never touch

# Perf: enumerate Win32_Process ONCE into a PID hashtable, then reuse everywhere.
# Prior version called Get-CimInstance Win32_Process -Filter ProcessId=X once per
# listener (~700ms each x 50 listeners = 35s) plus 3 full unfiltered enumerations.
# One bulk enumeration costs ~750ms; per-PID lookup is now a hashtable hit.
# See ~/.claude/rules/common/code-as-furniture.md - fix lands inline, not documented-and-left.
$procsByPid = @{}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $procsByPid[[int]$_.ProcessId] = $_
}
function Get-Cmdline([int]$ProcId) { $procsByPid[$ProcId].CommandLine }
function Get-ExeName([int]$ProcId) { $procsByPid[$ProcId].Name }

# memory_hub / atlas_map_api run as a launcher-parent + listener-child pair: the parent
# python.exe spawns a child python.exe that actually binds the port. "Not the port owner"
# is NOT a safe orphan signal for these - killing the parent kills the child (the live
# service on :3071/:3072) with it. Walk the ancestor chain of the port owner so the
# launcher parent is never mistaken for a leaked duplicate.
function Get-AncestorPids([int]$ProcId) {
    $ancestors = @()
    $cur = $ProcId
    for ($i = 0; $i -lt 10; $i++) {
        if (-not $cur -or $cur -eq 0 -or $cur -eq 4) { break }
        $proc = $procsByPid[$cur]
        if (-not $proc -or -not $proc.ParentProcessId) { break }
        $ancestors += [int]$proc.ParentProcessId
        $cur = [int]$proc.ParentProcessId
    }
    return $ancestors
}

# Get-TcpListeners is provided by _atlas_manifest.ps1 (hashtable: port -> pid).
# netstat -ano -p TCP is ~30x faster than Get-NetTCPConnection on this box
# (175ms vs 5200ms); the helper dedupes IPv4/IPv6 rows and skips PIDs 0/4.

$candidates = @()   # each: @{ Pid; Port; Reason; Cmdline }
$self = $PID
$listeners = Get-TcpListeners   # hashtable: port -> pid

# --- 1. Known squatters + any non-Atlas listener on an Atlas port ---
foreach ($port in $listeners.Keys) {
    $procId = $listeners[$port]
    if ($procId -eq $self) { continue }
    if ($WhitelistPorts -contains $port) { continue }
    $cmd = Get-Cmdline $procId
    if (-not $cmd) { continue }
    if ($port -eq 8799 -and $cmd -match 'iTunes-Titles-Backup') {
        $candidates += @{ ProcId = $procId; Port = $port; Reason = 'squatter: iTunes-Titles-Backup static server on :8799'; Cmdline = $cmd }
    }
    elseif ($port -eq 8765 -and $cmd -match '-m\s+http\.server\s+8765') {
        $candidates += @{ ProcId = $procId; Port = $port; Reason = 'squatter: bare python -m http.server on :8765'; Cmdline = $cmd }
    }
    elseif ($AtlasManifest.ContainsKey($port)) {
        if (-not (Test-CmdlineMatches -Cmdline $cmd -Matchers $AtlasManifest[$port].Matchers)) {
            $candidates += @{ ProcId = $procId; Port = $port; Reason = "non-Atlas listener on Atlas port :$port (expected $($AtlasManifest[$port].Name))"; Cmdline = $cmd }
        }
    }
}

# --- 2. Leaked DUPLICATE memory_hub.server / atlas_map_api.server PIDs ---
# Keep the PID that owns the service port; any other python.exe running the same module is a leak.
# Filter to python executables: the powershell.exe log-pipe wrappers ALSO contain the module
# string in their command lines and must never be killed.
$dupSpecs = @(
    @{ Module = '-m\s+memory_hub\.server';    Port = 3071 },
    @{ Module = '-m\s+atlas_map_api\.server'; Port = 3072 }
)
foreach ($spec in $dupSpecs) {
    $owner = if ($listeners.ContainsKey($spec.Port)) { $listeners[$spec.Port] } else { $null }
    $ownerAncestors = if ($owner) { Get-AncestorPids -ProcId $owner } else { @() }
    $ownerProc = if ($owner) { $procsByPid[[int]$owner] } else { $null }
    $ownerDirectParent = if ($ownerProc -and $ownerProc.ParentProcessId) { [int]$ownerProc.ParentProcessId } else { $null }
    foreach ($p in $procsByPid.Values) {
        if ($p.Name -notmatch '^python(\.exe)?$') { continue }
        if (-not $p.CommandLine -or $p.CommandLine -notmatch $spec.Module) { continue }
        if ($p.ProcessId -eq $owner) { continue }   # the live service - keep
        if ($ownerAncestors -contains $p.ProcessId) { continue }   # launcher/reloader parent chain - keep
        if ($ownerDirectParent -and $p.ProcessId -eq $ownerDirectParent) { continue }   # direct parent belt-and-suspenders - keep
        $candidates += @{ ProcId = $p.ProcessId; Port = $spec.Port; Reason = "duplicate $($spec.Module -replace '.*m.s.',''): not the :$($spec.Port) listener"; Cmdline = $p.CommandLine }
    }
}

# --- 3. Lingering bash wrappers that spawned the squatters (match on iTunes-Titles-Backup) ---
foreach ($w in $procsByPid.Values) {
    if ($w.Name -ne 'bash.exe') { continue }
    if (-not $w.CommandLine -or $w.CommandLine -notmatch 'iTunes-Titles-Backup.*http\.server') { continue }
    $candidates += @{ ProcId = $w.ProcessId; Port = $null; Reason = 'lingering bash wrapper that spawned a squatter'; Cmdline = $w.CommandLine }
}

# Dedup by PID
$seen = @{}; $candidates = @($candidates | Where-Object { -not $seen.ContainsKey($_.ProcId) -and ($seen[$_.ProcId] = $true) })

# --- Report ---
if ($candidates.Count -eq 0) {
    Write-Host 'No orphans found. Port scan is clean.' -ForegroundColor Green
    exit 0
}
Write-Host "`nOrphan candidates ($($candidates.Count)):" -ForegroundColor Cyan
foreach ($c in $candidates) {
    $portStr = if ($c.Port) { ":$($c.Port)" } else { '-' }
    Write-Host ("  PID {0,-7} {1,-6} {2}" -f $c.ProcId, $portStr, $c.Reason) -ForegroundColor Yellow
    Write-Host ("          {0}" -f ($c.Cmdline -replace '\s+', ' ').Substring(0, [Math]::Min(160, ($c.Cmdline -replace '\s+', ' ').Length))) -ForegroundColor DarkGray
}
if ($DryRun) {
    Write-Host "`n-DryRun: nothing killed." -ForegroundColor Green
    exit 0
}

# --- Confirm, then kill ---
if (-not $Force) {
    $answer = Read-Host "`nKill these $($candidates.Count) processes? (yes/no)"
    if ($answer -ne 'yes') { Write-Host 'Aborted.' -ForegroundColor Red; exit 1 }
}
foreach ($c in $candidates) {
    try {
        Stop-Process -Id $c.ProcId -Force -Confirm:$false -ErrorAction Stop
        Write-Host "  [killed] PID $($c.ProcId) ($($c.Reason))" -ForegroundColor Green
    } catch {
        Write-Host "  [gone/failed] PID $($c.ProcId): $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}
Write-Host "`nDone. Re-run with -DryRun to verify the scan is clean." -ForegroundColor Cyan
