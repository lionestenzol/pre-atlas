# Atlas — stop all standalone services.
$ErrorActionPreference = "Continue"
$ports = @(3000, 3001, 3002, 3004, 3005, 3006, 3007, 3008, 3009, 3010, 3030, 3050, 8887)

Write-Host ""
Write-Host "Stopping Atlas services on ports: $($ports -join ', ')" -ForegroundColor Cyan
Write-Host ""

$killed = 0
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $pidToKill = $conn.OwningProcess
        try {
            $proc = Get-Process -Id $pidToKill -ErrorAction Stop
            Stop-Process -Id $pidToKill -Force -ErrorAction Stop
            Write-Host "  [kill] PID $pidToKill ($($proc.ProcessName)) on :$port" -ForegroundColor Yellow
            $killed++
        } catch {}
    }
}

Write-Host ""
Write-Host "  Killed $killed processes." -ForegroundColor $(if ($killed -gt 0) {"Green"} else {"DarkGray"})
Write-Host ""
