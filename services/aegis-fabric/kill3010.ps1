$conns = Get-NetTCPConnection -LocalPort 3010 -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        $pid = $c.OwningProcess
        Write-Host "Killing PID $pid on port 3010"
        Stop-Process -Id $pid -Force
    }
} else {
    Write-Host "Nothing listening on 3010"
}

$conns2 = Get-NetTCPConnection -LocalPort 3001 -ErrorAction SilentlyContinue
if ($conns2) {
    foreach ($c in $conns2) {
        $pid = $c.OwningProcess
        Write-Host "Killing PID $pid on port 3001"
        Stop-Process -Id $pid -Force
    }
} else {
    Write-Host "Nothing listening on 3001"
}
