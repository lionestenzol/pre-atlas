$pgBin = "C:\Program Files\PostgreSQL\12\bin"
$env:PGPASSWORD = "admin"  # default postgres superuser password - may differ

# Try common superuser passwords
$passwords = @("admin", "postgres", "password", "root", "")
$connected = $false

foreach ($pw in $passwords) {
    $env:PGPASSWORD = $pw
    $result = & "$pgBin\psql.exe" -U postgres -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Connected to PostgreSQL with superuser password"
        $connected = $true
        break
    }
}

if (-not $connected) {
    # Try peer/trust auth (no password)
    $env:PGPASSWORD = ""
    $result = & "$pgBin\psql.exe" -U postgres -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Connected via trust auth"
        $connected = $true
    }
}

if (-not $connected) {
    Write-Host "ERROR: Cannot connect to PostgreSQL. Tried passwords: $($passwords -join ', ')"
    Write-Host "Please provide the postgres superuser password."
    exit 1
}

# Create aegis user
Write-Host "Creating aegis user..."
& "$pgBin\psql.exe" -U postgres -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aegis') THEN CREATE ROLE aegis LOGIN PASSWORD 'aegis_dev_pass' CREATEDB; END IF; END `$`$;"

# Create aegis_admin database
Write-Host "Creating aegis_admin database..."
$dbExists = & "$pgBin\psql.exe" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'aegis_admin'"
if ($dbExists -ne "1") {
    & "$pgBin\psql.exe" -U postgres -c "CREATE DATABASE aegis_admin OWNER aegis"
    Write-Host "Database aegis_admin created"
} else {
    Write-Host "Database aegis_admin already exists"
}

# Apply migration
Write-Host "Applying admin migration..."
$env:PGPASSWORD = "aegis_dev_pass"
& "$pgBin\psql.exe" -U aegis -d aegis_admin -f "C:\Users\bruke\Pre Atlas\services\aegis-fabric\db\migrations\001_admin.sql"

Write-Host "PostgreSQL setup complete!"
