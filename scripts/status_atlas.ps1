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
