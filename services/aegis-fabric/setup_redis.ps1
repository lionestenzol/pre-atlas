$projectDir = "C:\Users\bruke\Pre Atlas\services\aegis-fabric"
$redisDir = "$projectDir\tools\redis"

# Create directory
New-Item -ItemType Directory -Path $redisDir -Force | Out-Null

# Extract
Write-Host "Extracting Redis..."
Expand-Archive -Path "$projectDir\redis.zip" -DestinationPath $redisDir -Force

# Find redis-server.exe
$redisServer = Get-ChildItem $redisDir -Recurse -Filter "redis-server.exe" | Select-Object -First 1
if ($redisServer) {
    Write-Host "Found: $($redisServer.FullName)"
    # Start Redis in background
    Write-Host "Starting Redis..."
    Start-Process -FilePath $redisServer.FullName -WindowStyle Hidden
    Start-Sleep -Seconds 2
    # Test
    $redisCli = Join-Path $redisServer.DirectoryName "redis-cli.exe"
    if (Test-Path $redisCli) {
        $ping = & $redisCli ping 2>&1
        Write-Host "Redis PING: $ping"
    }
} else {
    Write-Host "redis-server.exe not found in extracted files"
    Get-ChildItem $redisDir -Recurse | Select-Object -ExpandProperty FullName | ForEach-Object { Write-Host $_ }
}
