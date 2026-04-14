# setup_n8n_workflows.ps1 — Create all 12 Pre Atlas n8n workflows
# Usage: powershell -File scripts/setup_n8n_workflows.ps1

$N8N_URL = "http://localhost:5678/api/v1"
$API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
$HEADERS = @{ "X-N8N-API-KEY" = $API_KEY; "Content-Type" = "application/json" }
$BASE = "C:\Users\bruke\Pre Atlas"
$CS = "$BASE\services\cognitive-sensor"

$created = 0
$failed = 0

function New-Workflow($name, $body) {
    try {
        $resp = Invoke-RestMethod -Uri "$N8N_URL/workflows" -Method Post -Headers $HEADERS -Body ($body | ConvertTo-Json -Depth 20)
        Write-Host "[OK] $name (id: $($resp.id))" -ForegroundColor Green
        $script:created++
        return $resp.id
    } catch {
        Write-Host "[FAIL] $name — $($_.Exception.Message)" -ForegroundColor Red
        $script:failed++
        return $null
    }
}

function Activate-Workflow($id) {
    if ($id) {
        try {
            Invoke-RestMethod -Uri "$N8N_URL/workflows/$id/activate" -Method Post -Headers $HEADERS | Out-Null
        } catch {
            Write-Host "  [WARN] Could not activate $id" -ForegroundColor Yellow
        }
    }
}

Write-Host "`n=== Pre Atlas n8n Workflow Setup ===" -ForegroundColor Cyan
Write-Host "Target: $N8N_URL`n"

# ──────────────────────────────────────────────
# 1. Morning Refresh (Daily @ 8:00 AM)
# ──────────────────────────────────────────────
$w1 = @{
    name = "01 — Morning Refresh"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "0 8 * * *" }
                    )
                }
            }
        },
        @{
            id = "run_daily"
            name = "Run Daily Pipeline"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$CS`" && python atlas_cli.py daily"
            }
        },
        @{
            id = "run_daemon"
            name = "Trigger Delta Daemon"
            type = "n8n-nodes-base.httpRequest"
            typeVersion = 4.2
            position = @(750, 300)
            parameters = @{
                url = "http://localhost:3001/api/daemon/run"
                method = "POST"
                options = @{ timeout = 30000 }
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Run Daily Pipeline"; type = "main"; index = 0 } )
            )
        }
        "Run Daily Pipeline" = @{
            main = @(
                @( @{ node = "Trigger Delta Daemon"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id1 = New-Workflow "01 — Morning Refresh" $w1

# ──────────────────────────────────────────────
# 2. Service Health Check (Every 15 min)
# ──────────────────────────────────────────────
$w2 = @{
    name = "02 — Service Health Check"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "*/15 * * * *" }
                    )
                }
            }
        },
        @{
            id = "check_all"
            name = "Check All Services"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = @"
powershell -Command "& {
    `$results = @()
    `$services = @(
        @{name='delta-kernel'; url='http://localhost:3001/api/health'},
        @{name='mirofish'; url='http://localhost:3003/api/v1/health'},
        @{name='openclaw'; url='http://localhost:3004/api/v1/health'},
        @{name='orchestrator'; url='http://localhost:3005/api/v1/health'}
    )
    foreach (`$svc in `$services) {
        try {
            `$r = Invoke-WebRequest -Uri `$svc.url -TimeoutSec 5 -UseBasicParsing
            `$results += @{name=`$svc.name; status='up'; code=`$r.StatusCode}
        } catch {
            `$results += @{name=`$svc.name; status='down'; code=0}
        }
    }
    `$results | ConvertTo-Json -Compress
}"
"@
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Check All Services"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id2 = New-Workflow "02 — Service Health Check" $w2

# ──────────────────────────────────────────────
# 3. Git Commit Digest (Daily @ 7:00 AM)
# ──────────────────────────────────────────────
$w3 = @{
    name = "03 — Git Commit Digest"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "0 7 * * *" }
                    )
                }
            }
        },
        @{
            id = "git_log"
            name = "Git Log"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$BASE`" && git log --oneline --since=`"1 day ago`" --all 2>&1 || echo `"No commits in last 24h`""
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Git Log"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id3 = New-Workflow "03 — Git Commit Digest" $w3

# ──────────────────────────────────────────────
# 4. Test Runner (Webhook)
# ──────────────────────────────────────────────
$w4 = @{
    name = "04 — Test Runner"
    nodes = @(
        @{
            id = "trigger"
            name = "Webhook"
            type = "n8n-nodes-base.webhook"
            typeVersion = 2
            position = @(250, 300)
            parameters = @{
                path = "test-runner"
                httpMethod = "POST"
            }
            webhookId = "test-runner"
        },
        @{
            id = "run_tests"
            name = "Run All Tests"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = @"
powershell -Command "& {
    `$results = @{}
    try { cd '$BASE\services\delta-kernel'; `$r = npm run test 2>&1; `$results['delta-kernel'] = if (`$LASTEXITCODE -eq 0) {'PASS'} else {'FAIL'} } catch { `$results['delta-kernel'] = 'ERROR' }
    try { cd '$BASE\services\openclaw'; `$r = python -m pytest --tb=no -q 2>&1; `$results['openclaw'] = if (`$LASTEXITCODE -eq 0) {'PASS'} else {'FAIL'} } catch { `$results['openclaw'] = 'ERROR' }
    try { cd '$BASE\services\aegis-fabric'; `$r = npm run test 2>&1; `$results['aegis-fabric'] = if (`$LASTEXITCODE -eq 0) {'PASS'} else {'FAIL'} } catch { `$results['aegis-fabric'] = 'ERROR' }
    `$results | ConvertTo-Json -Compress
}"
"@
            }
        }
    )
    connections = @{
        "Webhook" = @{
            main = @(
                @( @{ node = "Run All Tests"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id4 = New-Workflow "04 — Test Runner" $w4

# ──────────────────────────────────────────────
# 5. Conversation Intake (Webhook)
# ──────────────────────────────────────────────
$w5 = @{
    name = "05 — Conversation Intake"
    nodes = @(
        @{
            id = "trigger"
            name = "Webhook"
            type = "n8n-nodes-base.webhook"
            typeVersion = 2
            position = @(250, 300)
            parameters = @{
                path = "conversation-intake"
                httpMethod = "POST"
            }
            webhookId = "conversation-intake"
        },
        @{
            id = "run_pipeline"
            name = "Run Idea Pipeline"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$CS`" && python agent_excavator.py && python agent_deduplicator.py && python agent_classifier.py && python agent_orchestrator.py && python agent_reporter.py"
            }
        }
    )
    connections = @{
        "Webhook" = @{
            main = @(
                @( @{ node = "Run Idea Pipeline"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id5 = New-Workflow "05 — Conversation Intake" $w5

# ──────────────────────────────────────────────
# 6. Weekly Governor (Sunday @ 9:00 AM)
# ──────────────────────────────────────────────
$w6 = @{
    name = "06 — Weekly Governor"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "0 9 * * 0" }
                    )
                }
            }
        },
        @{
            id = "run_weekly"
            name = "Run Weekly Pipeline"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$CS`" && python atlas_cli.py weekly"
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Run Weekly Pipeline"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id6 = New-Workflow "06 — Weekly Governor" $w6

# ──────────────────────────────────────────────
# 7. Book Pipeline (Webhook)
# ──────────────────────────────────────────────
$w7 = @{
    name = "07 — Book Pipeline"
    nodes = @(
        @{
            id = "trigger"
            name = "Webhook"
            type = "n8n-nodes-base.webhook"
            typeVersion = 2
            position = @(250, 300)
            parameters = @{
                path = "book-pipeline"
                httpMethod = "POST"
            }
            webhookId = "book-pipeline"
        },
        @{
            id = "build_pdf"
            name = "Build Book PDF"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$BASE\data`" && python build_book_pdf.py"
            }
        }
    )
    connections = @{
        "Webhook" = @{
            main = @(
                @( @{ node = "Build Book PDF"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id7 = New-Workflow "07 — Book Pipeline" $w7

# ──────────────────────────────────────────────
# 8. Idea Triage (Webhook)
# ──────────────────────────────────────────────
$w8 = @{
    name = "08 — Idea Triage"
    nodes = @(
        @{
            id = "trigger"
            name = "Webhook"
            type = "n8n-nodes-base.webhook"
            typeVersion = 2
            position = @(250, 300)
            parameters = @{
                path = "idea-triage"
                httpMethod = "POST"
            }
            webhookId = "idea-triage"
        },
        @{
            id = "run_backlog"
            name = "Run Backlog Maintenance"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "cd `"$CS`" && python atlas_cli.py backlog"
            }
        }
    )
    connections = @{
        "Webhook" = @{
            main = @(
                @( @{ node = "Run Backlog Maintenance"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id8 = New-Workflow "08 — Idea Triage" $w8

# ──────────────────────────────────────────────
# 9. Mosaic Heartbeat (Every 5 min)
# ──────────────────────────────────────────────
$w9 = @{
    name = "09 — Mosaic Heartbeat"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "*/5 * * * *" }
                    )
                }
            }
        },
        @{
            id = "heartbeat"
            name = "Ping All Services"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = @"
powershell -Command "& {
    `$ts = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
    `$services = @(
        @{name='delta-kernel';port=3001;path='/api/health'},
        @{name='aegis-fabric';port=3002;path='/api/v1/health'},
        @{name='mirofish';port=3003;path='/api/v1/health'},
        @{name='openclaw';port=3004;path='/api/v1/health'},
        @{name='orchestrator';port=3005;path='/api/v1/health'}
    )
    `$results = @{timestamp=`$ts; services=@()}
    foreach (`$s in `$services) {
        `$sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            `$r = Invoke-WebRequest -Uri `"http://localhost:`$(`$s.port)`$(`$s.path)`" -TimeoutSec 5 -UseBasicParsing
            `$sw.Stop()
            `$results.services += @{name=`$s.name;status='up';ms=`$sw.ElapsedMilliseconds;code=`$r.StatusCode}
        } catch {
            `$sw.Stop()
            `$results.services += @{name=`$s.name;status='down';ms=`$sw.ElapsedMilliseconds;code=0}
        }
    }
    `$json = `$results | ConvertTo-Json -Depth 3 -Compress
    `$json | Out-File -FilePath '$CS\service_heartbeat.json' -Encoding utf8 -Force
    `$json
}"
"@
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Ping All Services"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id9 = New-Workflow "09 — Mosaic Heartbeat" $w9

# ──────────────────────────────────────────────
# 10. Festival Progress Sync (Daily @ 8:30 AM)
# ──────────────────────────────────────────────
$w10 = @{
    name = "10 — Festival Progress Sync"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "30 8 * * *" }
                    )
                }
            }
        },
        @{
            id = "fest_progress"
            name = "Fetch Festival Progress"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = "wsl -d Ubuntu -- bash -c `"cd /root/festival-project && fest progress 2>&1`""
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Fetch Festival Progress"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id10 = New-Workflow "10 — Festival Progress Sync" $w10

# ──────────────────────────────────────────────
# 11. Webhook Relay (Generic)
# ──────────────────────────────────────────────
$w11 = @{
    name = "11 — Webhook Relay"
    nodes = @(
        @{
            id = "trigger"
            name = "Webhook"
            type = "n8n-nodes-base.webhook"
            typeVersion = 2
            position = @(250, 300)
            parameters = @{
                path = "relay"
                httpMethod = "POST"
            }
            webhookId = "relay"
        },
        @{
            id = "forward"
            name = "Forward Request"
            type = "n8n-nodes-base.httpRequest"
            typeVersion = 4.2
            position = @(500, 300)
            parameters = @{
                url = "={{ `$json.body.target_url }}"
                method = "POST"
                sendBody = $true
                bodyParameters = @{
                    parameters = @(
                        @{ name = "payload"; value = "={{ JSON.stringify(`$json.body.payload) }}" }
                    )
                }
                options = @{ timeout = 30000 }
            }
        }
    )
    connections = @{
        "Webhook" = @{
            main = @(
                @( @{ node = "Forward Request"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id11 = New-Workflow "11 — Webhook Relay" $w11

# ──────────────────────────────────────────────
# 12. Scheduled Backup (Daily @ 2:00 AM)
# ──────────────────────────────────────────────
$w12 = @{
    name = "12 — Scheduled Backup"
    nodes = @(
        @{
            id = "trigger"
            name = "Schedule"
            type = "n8n-nodes-base.scheduleTrigger"
            typeVersion = 1.2
            position = @(250, 300)
            parameters = @{
                rule = @{
                    interval = @(
                        @{ field = "cronExpression"; expression = "0 2 * * *" }
                    )
                }
            }
        },
        @{
            id = "backup"
            name = "Run Backup"
            type = "n8n-nodes-base.executeCommand"
            typeVersion = 1
            position = @(500, 300)
            parameters = @{
                command = @"
powershell -Command "& {
    `$date = Get-Date -Format 'yyyy-MM-dd'
    `$dir = '$BASE\backups\' + `$date
    New-Item -ItemType Directory -Force -Path `$dir | Out-Null
    `$files = @(
        'C:\Users\bruke\.n8n\database.sqlite',
        '$CS\cognitive_state.json',
        '$CS\governance_state.json',
        '$CS\idea_registry.json',
        '$CS\atlas_state.json',
        '$CS\daily_payload.json'
    )
    `$copied = 0
    foreach (`$f in `$files) {
        if (Test-Path `$f) {
            Copy-Item `$f -Destination `$dir -Force
            `$copied++
        }
    }
    # Clean backups older than 7 days
    Get-ChildItem '$BASE\backups' -Directory | Where-Object { `$_.CreationTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Recurse -Force
    `$size = (Get-ChildItem `$dir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Output `"Backup complete: `$copied files, `$([math]::Round(`$size,2)) MB -> `$dir`"
}"
"@
            }
        }
    )
    connections = @{
        "Schedule" = @{
            main = @(
                @( @{ node = "Run Backup"; type = "main"; index = 0 } )
            )
        }
    }
    settings = @{ executionOrder = "v1" }
}
$id12 = New-Workflow "12 — Scheduled Backup" $w12

# ──────────────────────────────────────────────
# Activate scheduled workflows
# ──────────────────────────────────────────────
Write-Host "`nActivating scheduled workflows..." -ForegroundColor Cyan
@($id1, $id2, $id3, $id6, $id9, $id10, $id12) | ForEach-Object { Activate-Workflow $_ }

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Created: $created / 12"
if ($failed -gt 0) { Write-Host "Failed: $failed" -ForegroundColor Red }
Write-Host "Scheduled (auto): Morning Refresh, Health Check, Git Digest, Weekly Governor, Heartbeat, Festival Sync, Backup"
Write-Host "On-demand (webhook): Test Runner, Conversation Intake, Book Pipeline, Idea Triage, Webhook Relay"
Write-Host "`nView at: http://localhost:5678"
