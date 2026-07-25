# _atlas_manifest.ps1 - shared manifest + listener helpers.
#
# Dot-source this from other Atlas scripts:
#   . "$PSScriptRoot\_atlas_manifest.ps1"
#
# Exposes:
#   Get-AtlasManifest [-RepoRoot <path>]
#     -> hashtable keyed by port, value = pscustomobject with
#        Name / Port / Cwd / Matcher / Matchers / Argv / Exec.
#     Reads .claude/launch.json (single source of truth for 38+ surfaces).
#
#   Get-TcpListeners
#     -> hashtable keyed by port, value = owning PID.
#     Uses netstat -ano (~30x faster than Get-NetTCPConnection).
#
#   Test-CmdlineMatches [-Cmdline <s>] [-Matchers <array>]
#     -> $true if any matcher token appears in $Cmdline after normalizing
#        forward slashes to back slashes (case-insensitive).
#
# See ~/.claude/rules/common/code-as-furniture.md - one manifest, one place.

function Get-AtlasManifest {
    param([string]$RepoRoot)
    if (-not $RepoRoot) {
        # Default: parent of the scripts/ directory this file lives in.
        $RepoRoot = Split-Path -Parent $PSScriptRoot
    }
    $launchJson = Join-Path $RepoRoot ".claude\launch.json"
    if (-not (Test-Path $launchJson)) {
        throw "launch.json not found at $launchJson"
    }
    $launch = Get-Content -Raw $launchJson | ConvertFrom-Json
    $declared = @{}
    foreach ($cfg in $launch.configurations) {
        if (-not $cfg.port) { continue }
        $port = [int]$cfg.port

        # Multi-signal matcher list. See scan_atlas_live.ps1 header for why:
        # http-server surfaces vary path separators, uvicorn strips ":app"
        # off -m invocations, and some surfaces ("run dev") have no
        # distinctive arg. Match succeeds if cmdline contains ANY candidate.
        $matchers = New-Object System.Collections.ArrayList
        foreach ($a in $cfg.runtimeArgs) {
            if ($a -match '^-') { continue }
            if ($a.Length -le 3) { continue }
            [void]$matchers.Add($a)
            if ($a -match '^(.+):[a-zA-Z_][a-zA-Z0-9_]*$') { [void]$matchers.Add($matches[1]) }
            $base = $a -replace '.*[\\/]', ''
            if ($base -ne $a -and $base.Length -gt 3) { [void]$matchers.Add($base) }
        }
        if ($cfg.cwd) {
            $cwdBase = ($cfg.cwd -replace '.*[\\/]', '')
            if ($cwdBase.Length -gt 2) { [void]$matchers.Add($cwdBase) }
        }
        [void]$matchers.Add("$port")
        $seen = @{}
        $matchers = @($matchers | Where-Object { -not $seen.ContainsKey($_) -and ($seen[$_] = $true) })

        # Resolve cwd
        $cwd = $null
        if ($cfg.cwd) {
            if ([System.IO.Path]::IsPathRooted($cfg.cwd)) { $cwd = $cfg.cwd }
            else { $cwd = Join-Path $RepoRoot $cfg.cwd }
        }
        if (-not $cwd -and $cfg.runtimeArgs -and ($cfg.runtimeArgs -join ' ') -match 'http-server') {
            $dirArg = $cfg.runtimeArgs | Where-Object { $_ -notmatch '^-' -and $_ -notmatch 'http-server' } | Select-Object -First 1
            if ($dirArg) {
                if ([System.IO.Path]::IsPathRooted($dirArg)) { $cwd = $dirArg }
                else { $cwd = Join-Path $RepoRoot $dirArg }
            }
        }

        $declared[$port] = [pscustomobject]@{
            Name     = $cfg.name
            Port     = $port
            Cwd      = $cwd
            Matcher  = $matchers[0]
            Matchers = $matchers
            Argv     = ($cfg.runtimeArgs -join ' ')
            Exec     = $cfg.runtimeExecutable
        }
    }
    return $declared
}

function Get-TcpListeners {
    # Dedupe by (port, pid) across IPv4/IPv6 rows. Skip system PIDs 0 and 4.
    $seen = @{}
    $out = @{}
    foreach ($line in (netstat -ano -p TCP 2>$null)) {
        if ($line -notmatch '^\s+TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$') { continue }
        $port = [int]$matches[1]; $procId = [int]$matches[2]
        if ($procId -eq 0 -or $procId -eq 4) { continue }
        $key = "$port/$procId"
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (-not $out.ContainsKey($port)) { $out[$port] = $procId }
    }
    return $out
}

function Test-CmdlineMatches {
    param(
        [string]$Cmdline,
        [array]$Matchers
    )
    if (-not $Cmdline) { return $false }
    $cmdN = $Cmdline -replace '/', '\'
    foreach ($m in $Matchers) {
        if (-not $m) { continue }
        $mN = $m -replace '/', '\'
        if ($cmdN.IndexOf($mN, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    }
    return $false
}
