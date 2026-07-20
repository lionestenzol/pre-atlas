<#
.SYNOPSIS
    Optogon stack health audit. Local-only (reads SQLite, hits :3010, walks files).

.DESCRIPTION
    Reports four dimensions and writes a Markdown report:
      1. Path library growth vs the 2026-04-27 baseline of 5 paths
      2. Miss queue (/pending_path_requests) - top 5 recent + duplicates >=3
      3. Wedged sessions (started but not closed in N days)
      4. MCP server importability

.NOTES
    Run now:
        powershell -NoProfile -File "C:\Users\bruke\Pre Atlas\tools\optogon-audit\audit.ps1"

    Register as a one-time task on 2026-05-11 at 9 AM local:
        $a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\bruke\Pre Atlas\tools\optogon-audit\audit.ps1"'
        $t = New-ScheduledTaskTrigger -Once -At "2026-05-11 09:00"
        Register-ScheduledTask -TaskName "Optogon Audit" -Action $a -Trigger $t

    Re-arm for another date:
        Set-ScheduledTask -TaskName "Optogon Audit" -Trigger (New-ScheduledTaskTrigger -Once -At "2026-05-25 09:00")

    Unregister:
        Unregister-ScheduledTask -TaskName "Optogon Audit" -Confirm:$false
#>

[CmdletBinding()]
param(
    [string]$RepoRoot = "C:\Users\bruke\Pre Atlas",
    [string]$ReportDir = (Join-Path $env:USERPROFILE ".claude\reports"),
    [int]$OptogonPort = 3010,
    [int]$WedgeDays = 3,
    [int]$BaselinePathCount = 5
)

$ErrorActionPreference = "Continue"
$today = Get-Date -Format "yyyy-MM-dd"
$reportPath = Join-Path $ReportDir "optogon-audit-$today.md"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$buf = New-Object System.Text.StringBuilder
function Out-Both {
    param([string]$Text = "")
    [void]$buf.AppendLine($Text)
    Write-Host $Text
}

Out-Both "# Optogon stack audit - $today"
Out-Both ""
Out-Both "Repo: $RepoRoot"
Out-Both ""

# ---------------------------------------------------------------------------
# 1. Path library growth
# ---------------------------------------------------------------------------
Out-Both "## 1. Path library"
Out-Both ""
$pathsDir = Join-Path $RepoRoot "services\optogon\paths"
$newPaths = @()
$delta = -$BaselinePathCount
$count = 0
if (Test-Path $pathsDir) {
    $pathFiles = Get-ChildItem -Path $pathsDir -Filter "*.json" -ErrorAction SilentlyContinue |
                 Where-Object { -not $_.Name.StartsWith("_") }
    $count = $pathFiles.Count
    $delta = $count - $BaselinePathCount

    if ($delta -le 0) {
        Out-Both "Library: $count paths (baseline $BaselinePathCount, delta $delta)"
        Out-Both ""
        Out-Both "_No new paths authored since baseline._"
    } else {
        Out-Both "Library: $count paths (baseline $BaselinePathCount, +$delta new)"
        Out-Both ""
        $baseline = @("commit_a_file", "delegate_to_codex", "ship_inpact_lesson", "teach_me_a_path", "triage_fs_loop")
        foreach ($f in $pathFiles) {
            $id = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
            if ($baseline -notcontains $id) {
                try {
                    $data = Get-Content $f.FullName -Raw | ConvertFrom-Json
                    $trigger = ($data.entry.match_conditions | Select-Object -First 1).value
                    $threshold = $data.entry.match_threshold
                    $newPaths += [PSCustomObject]@{ id = $id; trigger = $trigger; threshold = $threshold }
                } catch {
                    $newPaths += [PSCustomObject]@{ id = $id; trigger = "<unparseable>"; threshold = "?" }
                }
            }
        }
        Out-Both "New paths since baseline:"
        foreach ($p in $newPaths) {
            Out-Both ("- {0}  trigger={1}  threshold={2}" -f $p.id, $p.trigger, $p.threshold)
        }
    }
} else {
    Out-Both "**WARNING:** paths dir not found at $pathsDir"
}
Out-Both ""

# ---------------------------------------------------------------------------
# 2. Miss queue (requires Optogon running on :3010)
# ---------------------------------------------------------------------------
Out-Both "## 2. Miss queue"
Out-Both ""
$queueAvailable = $false
$dupes = @()
$queueUrl = "http://127.0.0.1:$OptogonPort/pending_path_requests"
try {
    $queue = Invoke-RestMethod -Uri $queueUrl -TimeoutSec 5 -ErrorAction Stop
    $queueAvailable = $true
    if ($queue -isnot [array]) { $queue = @($queue) }
    Out-Both "Unresolved misses: $($queue.Count)"
    if ($queue.Count -gt 0) {
        Out-Both ""
        Out-Both "Most recent (top 5):"
        $queue | Select-Object -First 5 | ForEach-Object {
            Out-Both ("- {0}  ({1})" -f $_.input, $_.id)
        }
        $dupes = $queue | Group-Object -Property input |
                 Where-Object { $_.Count -ge 3 } |
                 Sort-Object -Property Count -Descending
        if ($dupes) {
            Out-Both ""
            Out-Both "**Strong teach-me candidates (>=3 occurrences):**"
            foreach ($d in $dupes) {
                Out-Both ("- {0}  -  {1} times" -f $d.Name, $d.Count)
            }
        }
    }
} catch {
    Out-Both "Optogon not reachable on :$OptogonPort. (Skipped queue check.)"
    Out-Both ""
    Out-Both "Boot Optogon with:"
    Out-Both ""
    Out-Both ("    cd `"{0}\services\optogon`"" -f $RepoRoot)
    Out-Both '    $env:PYTHONPATH = "src"'
    Out-Both "    python -m uvicorn optogon.main:app --port 3010"
}
Out-Both ""

# ---------------------------------------------------------------------------
# 3. Wedged sessions (via _wedged.py helper)
# ---------------------------------------------------------------------------
Out-Both "## 3. Wedged sessions"
Out-Both ""
$dbPath = Join-Path $RepoRoot "services\optogon\data\sessions.db"
$wedgedCount = 0
$wedgedOldest = $null
if (Test-Path $dbPath) {
    $helperPath = Join-Path $PSScriptRoot "_wedged.py"
    $rawJson = & python $helperPath $dbPath $WedgeDays 2>&1
    $exit = $LASTEXITCODE
    if ($exit -eq 0) {
        try {
            $wedged = $rawJson | ConvertFrom-Json
            if ($wedged -isnot [array]) { $wedged = @($wedged) }
            $wedgedCount = $wedged.Count
            if ($wedgedCount -eq 0) {
                Out-Both "No sessions stuck >$WedgeDays days."
            } else {
                Out-Both "**$wedgedCount** session(s) stuck >$WedgeDays days:"
                Out-Both ""
                $wedged | Select-Object -First 5 | ForEach-Object {
                    Out-Both ("- {0}  path={1}  node={2}  updated={3}" -f $_.session_id, $_.path_id, $_.current_node, $_.updated_at)
                }
                $wedgedOldest = $wedged[0]
            }
        } catch {
            Out-Both "Could not parse wedged-session output: $rawJson"
        }
    } else {
        Out-Both "Wedged-session query failed (python exit=$exit): $rawJson"
    }
} else {
    Out-Both "Sessions DB not found at $dbPath. (Optogon hasn't run yet.)"
}
Out-Both ""

# ---------------------------------------------------------------------------
# 4. MCP server health
# ---------------------------------------------------------------------------
Out-Both "## 4. MCP server"
Out-Both ""
$srcDir = Join-Path $RepoRoot "services\optogon\src"
$mcpFile = Join-Path $srcDir "optogon\mcp_server.py"
$mcpOk = $false
if (Test-Path $mcpFile) {
    $env:PYTHONPATH = $srcDir
    $mcpOut = & python -c "from optogon import mcp_server; import asyncio; t = asyncio.run(mcp_server.list_tools()); print('ok'); print(len(t), 'tools')" 2>&1
    $mcpExit = $LASTEXITCODE
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    if ($mcpExit -eq 0 -and ($mcpOut -join "`n") -match 'ok') {
        $mcpOk = $true
        $toolLine = ($mcpOut | Select-String "tools" | Select-Object -First 1).Line
        Out-Both "Importable: yes  ($toolLine)"
    } else {
        Out-Both "Importable: no  ($mcpOut)"
    }
} else {
    Out-Both "mcp_server.py not found at $mcpFile"
}
Out-Both ""

# ---------------------------------------------------------------------------
# 5. Recommendation
# ---------------------------------------------------------------------------
Out-Both "## Recommendation"
Out-Both ""
if ($dupes -and $dupes.Count -gt 0) {
    $top = $dupes[0]
    Out-Both ("**Author a path for `"{0}`"** ({1} repeated misses)." -f $top.Name, $top.Count)
    Out-Both ""
    Out-Both "Run in Claude Code:"
    Out-Both ""
    Out-Both ("    optogon_route(`"teach me a new path`")")
    Out-Both ("    then provide trigger phrase: {0}" -f $top.Name)
} elseif ($wedgedCount -gt 0) {
    Out-Both "**Resolve $wedgedCount stuck session(s)** - oldest at node `"$($wedgedOldest.current_node)`". Advance them via /session/{id}/turn or close them out."
} elseif (-not $mcpOk) {
    Out-Both "**Fix the MCP server import** before anything else - Claude Code's optogon_* tools are dead until this is green."
} elseif (-not $queueAvailable -and $delta -le 0) {
    Out-Both "**Boot Optogon and use it.** No new paths authored, no queue data. The library is sitting idle. Cheapest thing that compounds: route at least one routine task through optogon_route to start the preference store."
} elseif ($delta -gt 0) {
    Out-Both "**Library is growing - keep going.** $delta new path(s) since baseline. Schedule another audit in 2 weeks (Set-ScheduledTask, see script header)."
} else {
    Out-Both "All clean. Schedule another audit in 2 weeks (see script header for re-arm command)."
}
Out-Both ""
Out-Both "---"
Out-Both ("_Generated {0} by tools/optogon-audit/audit.ps1_" -f (Get-Date -Format "yyyy-MM-dd HH:mm"))

# ---------------------------------------------------------------------------
# Write report + best-effort toast
# ---------------------------------------------------------------------------
$buf.ToString() | Out-File -FilePath $reportPath -Encoding utf8
Write-Host ""
Write-Host "Report written: $reportPath"

try {
    $title = "Optogon audit ready"
    if ($dupes -and $dupes.Count -gt 0) {
        $body = "$($dupes.Count) teach-me candidate(s) found"
    } elseif ($delta -gt 0) {
        $body = "+$delta new path(s) since baseline"
    } else {
        $body = "Report ready - no new paths"
    }
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode($title)) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode($body)) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Optogon").Show($toast)
} catch {
    # Toast is nice-to-have; ignore failures
}
