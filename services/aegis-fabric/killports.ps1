$ports = @(3001, 3010)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($c in $connections) {
            $procId = $c.OwningProcess
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            Write-Host "Port $port -> PID $procId ($($proc.ProcessName)) - killing..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Port $port is free"
    }
}
