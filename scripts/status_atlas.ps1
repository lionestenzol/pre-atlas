# Atlas — show what's running right now.
$services = @(
    @{ Name = "mosaic-dashboard"; Port = 3000 },
    @{ Name = "delta-kernel";     Port = 3001 },
    @{ Name = "aegis-fabric";     Port = 3002 },
    @{ Name = "openclaw";         Port = 3004 },
    @{ Name = "mosaic-orch";      Port = 3005 },
    @{ Name = "inpact";           Port = 3006 },
    @{ Name = "code-converter";   Port = 3007 },
    @{ Name = "uasc";             Port = 3008 },
    @{ Name = "cortex";           Port = 3009 },
    @{ Name = "optogon";          Port = 3010 },
    @{ Name = "blueprint-gen";    Port = 3030 },
    @{ Name = "canvas-engine";    Port = 3050 },
    @{ Name = "atlas-substrate";  Port = 8887 }
)

Write-Host ""
Write-Host "ATLAS status" -ForegroundColor Cyan
Write-Host "------------" -ForegroundColor DarkGray

$up = 0
foreach ($s in $services) {
    $listen = Get-NetTCPConnection -State Listen -LocalPort $s.Port -ErrorAction SilentlyContinue
    if ($listen) {
        Write-Host ("  [UP  ] {0,-18} :{1,-5} PID {2}" -f $s.Name, $s.Port, $listen.OwningProcess) -ForegroundColor Green
        $up++
    } else {
        Write-Host ("  [DOWN] {0,-18} :{1}" -f $s.Name, $s.Port) -ForegroundColor DarkGray
    }
}
Write-Host ""
Write-Host "  $up of $($services.Count) up" -ForegroundColor $(if ($up -eq $services.Count) {"Green"} else {"Yellow"})
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
