# NOTE (2026-07-26, fest atlas-doors-AD0001/003_TRUST/03_retire): this script uses
# `npx tsx services/delta-kernel/src/cli/atlas-ai.ts agent --daemon --interval 60`
# because `atlas.exe agent --daemon` from the compiled Human door does not currently
# accept `--interval`. Kept as-is so the daemon keeps working; migrate to
# `atlas agent --daemon --interval 60` once the CLI teaches the interval flag.
# See ~/.claude/rules/common/code-as-furniture.md — headstone, not orphan.

$ErrorActionPreference = "Stop"

# Check Ollama
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3
    Write-Host "[OK] Ollama is running"
} catch {
    Write-Host "[INFO] Starting Ollama..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
        Write-Host "[OK] Ollama started"
    } catch {
        Write-Host "[WARN] Ollama failed to start — agent will run without LLM compounds"
    }
}

# Set env
$env:ATLAS_LLM_ENDPOINT = "http://localhost:11434"
$env:ATLAS_LLM_MODEL = "llama3.1:8b"

# Start agent daemon
Set-Location "$PSScriptRoot\.."
Write-Host "[START] atlas-ai agent daemon (interval=60s)"
npx tsx services/delta-kernel/src/cli/atlas-ai.ts agent --daemon --interval 60
