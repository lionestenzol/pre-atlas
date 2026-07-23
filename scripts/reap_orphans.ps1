# reap_orphans.ps1 - kill orphaned/duplicate dev servers so a port scan reflects Atlas only.
# Wave 0.3, atlas-consolidation-AC0002. Allow-list derived from scripts/start_atlas.ps1 ($services, lines 20-34).
# Never touches :5173 (noutube-native) or any process whose cmdline matches the Atlas allow-list.
# See ~/.claude/rules/common/code-as-furniture.md - re-detects at run time; PIDs are never hardcoded.
param(
    [switch]$DryRun,
    [switch]$Force   # skip the confirmation prompt (for automation)
)
$ErrorActionPreference = 'Stop'

# --- Allow-list: one regex per service command in start_atlas.ps1 ---
$AtlasPorts = @{
    3001 = 'src[/\\]api[/\\]server\.ts'                       # delta-kernel (npx tsx src/api/server.ts)
    3002 = 'src[/\\]api[/\\]server\.ts'                       # aegis-fabric
    3004 = 'uvicorn\s+openclaw\.api:app'                      # openclaw
    3006 = 'http-server.*-p\s*3006'                           # inpact
    3007 = 'server\.py'                                       # code-converter
    3008 = 'server\.py\s+--port\s+3008'                       # uasc
    3009 = 'uvicorn\s+cortex\.main:app'                       # cortex
    3010 = 'uvicorn\s+optogon\.main:app'                      # optogon
    3050 = 'canvas-engine'                                    # canvas-engine (tsx src/server.ts under canvas-engine)
    3071 = '-m\s+memory_hub\.server'                          # memory-hub
    3072 = '-m\s+atlas_map_api\.server'                       # atlas-map-api
    8887 = 'serve\.py'                                        # atlas-substrate (C:\Users\bruke\atlas)
}
$WhitelistPorts = @(5173)   # noutube-native Electron app - never touch

function Get-Cmdline([int]$ProcId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue).CommandLine
}
function Get-ExeName([int]$ProcId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue).Name
}

# memory_hub / atlas_map_api run as a launcher-parent + listener-child pair: the parent
# python.exe spawns a child python.exe that actually binds the port. "Not the port owner"
# is NOT a safe orphan signal for these - killing the parent kills the child (the live
# service on :3071/:3072) with it. Walk the ancestor chain of the port owner so the
# launcher parent is never mistaken for a leaked duplicate.
# See ~/.claude/rules/common/code-as-furniture.md - fix lands inline, not documented-and-left.
function Get-AncestorPids([int]$ProcId) {
    $ancestors = @()
    $cur = $ProcId
    for ($i = 0; $i -lt 10; $i++) {
        if (-not $cur -or $cur -eq 0 -or $cur -eq 4) { break }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
        if (-not $proc -or -not $proc.ParentProcessId) { break }
        $ancestors += [int]$proc.ParentProcessId
        $cur = [int]$proc.ParentProcessId
    }
    return $ancestors
}

$candidates = @()   # each: @{ Pid; Port; Reason; Cmdline }
$self = $PID

# --- 1. Known squatters + any non-Atlas listener on an Atlas port ---
$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalPort, OwningProcess -Unique
foreach ($l in $listeners) {
    if ($l.OwningProcess -eq $self -or $l.OwningProcess -eq 0 -or $l.OwningProcess -eq 4) { continue }
    if ($WhitelistPorts -contains $l.LocalPort) { continue }
    $cmd = Get-Cmdline $l.OwningProcess
    if (-not $cmd) { continue }
    if ($l.LocalPort -eq 8799 -and $cmd -match 'iTunes-Titles-Backup') {
        $candidates += @{ ProcId = $l.OwningProcess; Port = $l.LocalPort; Reason = 'squatter: iTunes-Titles-Backup static server on :8799'; Cmdline = $cmd }
    }
    elseif ($l.LocalPort -eq 8765 -and $cmd -match '-m\s+http\.server\s+8765') {
        $candidates += @{ ProcId = $l.OwningProcess; Port = $l.LocalPort; Reason = 'squatter: bare python -m http.server on :8765'; Cmdline = $cmd }
    }
    elseif ($AtlasPorts.ContainsKey([int]$l.LocalPort)) {
        if ($cmd -notmatch $AtlasPorts[[int]$l.LocalPort]) {
            $candidates += @{ ProcId = $l.OwningProcess; Port = $l.LocalPort; Reason = "non-Atlas listener on Atlas port :$($l.LocalPort)"; Cmdline = $cmd }
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
    $owner = (Get-NetTCPConnection -State Listen -LocalPort $spec.Port -ErrorAction SilentlyContinue |
        Select-Object -First 1).OwningProcess
    # Exclude the owner's whole ancestor chain (launcher parent, its parent, etc.) - these
    # are the reloader/launcher processes that spawned the listener, not leaked duplicates.
    $ownerAncestors = if ($owner) { Get-AncestorPids -ProcId $owner } else { @() }
    $ownerProc = if ($owner) { Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue } else { $null }
    $ownerDirectParent = if ($ownerProc -and $ownerProc.ParentProcessId) { [int]$ownerProc.ParentProcessId } else { $null }
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match $spec.Module -and $_.Name -match '^python(\.exe)?$'
    }
    foreach ($p in $procs) {
        if ($p.ProcessId -eq $owner) { continue }   # the live service - keep
        if ($ownerAncestors -contains $p.ProcessId) { continue }   # launcher/reloader parent chain - keep
        if ($ownerDirectParent -and $p.ProcessId -eq $ownerDirectParent) { continue }   # direct parent belt-and-suspenders - keep
        $candidates += @{ ProcId = $p.ProcessId; Port = $spec.Port; Reason = "duplicate $($spec.Module -replace '.*m.s.',''): not the :$($spec.Port) listener"; Cmdline = $p.CommandLine }
    }
}

# --- 3. Lingering bash wrappers that spawned the squatters (match on iTunes-Titles-Backup) ---
$wrappers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq 'bash.exe' -and $_.CommandLine -match 'iTunes-Titles-Backup.*http\.server'
}
foreach ($w in $wrappers) {
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
