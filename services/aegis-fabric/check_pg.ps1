$pgBin = "C:\Program Files\PostgreSQL\12\bin"
if (Test-Path "$pgBin\pg_isready.exe") {
    & "$pgBin\pg_isready.exe"
} else {
    Write-Host "pg_isready not found at $pgBin"
    # Try to find it
    Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "pg_isready.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
}

# Check if service is running
Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType
