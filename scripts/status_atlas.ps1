# Atlas - show what's running right now.
# Surface list is derived from .claude/launch.json via _atlas_manifest.ps1 so
# this stays in sync with reap_orphans.ps1 and scan_atlas_live.ps1 - previously
# had a hardcoded 13-service list that had drifted 25+ surfaces behind reality.
. "$PSScriptRoot\_atlas_manifest.ps1"

$declared  = Get-AtlasManifest
$listeners = Get-TcpListeners

Write-Host ""
Write-Host "ATLAS status" -ForegroundColor Cyan
Write-Host "------------" -ForegroundColor DarkGray

$up = 0
foreach ($port in ($declared.Keys | Sort-Object)) {
    $d = $declared[$port]
    if ($listeners.ContainsKey($port)) {
        Write-Host ("  [UP  ] {0,-24} :{1,-5} PID {2}" -f $d.Name, $port, $listeners[$port]) -ForegroundColor Green
        $up++
    } else {
        Write-Host ("  [DOWN] {0,-24} :{1}" -f $d.Name, $port) -ForegroundColor DarkGray
    }
}
Write-Host ""
Write-Host "  $up of $($declared.Count) up" -ForegroundColor $(if ($up -eq $declared.Count) {"Green"} else {"Yellow"})
Write-Host ""

# --- Scheduled tasks (Wave 1.3: unified status surface) ---
Write-Host "  Scheduled tasks" -ForegroundColor Cyan
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $_.TaskName -match '^(Atlas|PreAtlas)' -or $_.TaskName -eq 'Optogon Audit'
}
foreach ($t in $tasks) {
    $trig = ($t.Triggers | ForEach-Object {
        $kind = $_.CimClass.CimClassName -replace '^MSFT_Task', '' -replace 'Trigger$', ''
        if ($_.StartBoundary) { "$kind@$($_.StartBoundary)" } else { $kind }
    }) -join ', '
    if (-not $trig) { $trig = '(no trigger)' }
    $color = 'DarkGray'
    if ("$($t.State)" -eq 'Ready' -or "$($t.State)" -eq 'Running') { $color = 'Green' }
    Write-Host ("  [{0,-8}] {1,-36} {2}" -f $t.State, $t.TaskName, $trig) -ForegroundColor $color
}
Write-Host ""

# --- Governance daemon heartbeat (delta-kernel :3001) ---
Write-Host "  Governance daemon" -ForegroundColor Cyan
try {
    $tok = (Invoke-RestMethod -Uri 'http://127.0.0.1:3001/api/auth/token' -TimeoutSec 3).token
    $headers = @{}
    if ($tok) { $headers['Authorization'] = "Bearer $tok" }
    $d = Invoke-RestMethod -Uri 'http://127.0.0.1:3001/api/daemon/status' -Headers $headers -TimeoutSec 3
    $hbText = 'never'
    if ($d.last_heartbeat) {
        $hb = [DateTimeOffset]::FromUnixTimeMilliseconds([long]$d.last_heartbeat).LocalDateTime
        $ageMin = [int]((Get-Date) - $hb).TotalMinutes
        $hbText = "$hb ($ageMin m ago)"
    }
    $dColor = 'Yellow'
    if ($d.running) { $dColor = 'Green' }
    Write-Host ("  running={0}  last_heartbeat={1}" -f $d.running, $hbText) -ForegroundColor $dColor
} catch {
    Write-Host "  delta-kernel :3001 unreachable - daemon state unknown" -ForegroundColor DarkGray
}
Write-Host ""

# --- Orphan listeners (reuse Wave 0.3 detection, report-only) ---
Write-Host "  Orphan scan (reap_orphans.ps1 -DryRun)" -ForegroundColor Cyan
& "$PSScriptRoot\reap_orphans.ps1" -DryRun
