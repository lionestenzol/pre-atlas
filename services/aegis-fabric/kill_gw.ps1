$conns = Get-NetTCPConnection -LocalPort 3010 -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -ne 0 }
    foreach ($p in $pids) {
        Write-Host "Killing PID $p on port 3010"
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "Port 3010 is free"
}
