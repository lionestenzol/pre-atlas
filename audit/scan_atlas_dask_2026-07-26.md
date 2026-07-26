# Atlas recon scan · 2026-07-26T06:31:10+00:00

- Subsystems scanned: **60**
- Total wall time: **151.23s** across **8** Dask workers
- Zoekt path used: **True** (index: `C:\Users\bruke\zoekt-win\index`)
- Total code LOC (tokei): **554,323**
- Total data LOC (JSON/YAML/XML/MD/HTML, excluded from code): **4,687,997**
- Total files (walk): **82,746**
- Total TODOs/FIXMEs: **179**
- Total symbols: **244,793** (zoekt for TS/JS, ctags for the rest)
- Secret-pattern hits: **5** (review before ignoring)

## Per-subsystem summary

| Subsystem | Lang | LOC | Files | Symbols (via) | TODOs | Secrets | 30d commits | Port |
|---|---|---:|---:|---|---:|---:|---:|---:|
| _root | html | 308,958 | 77,918 | 0 (ctags) | 106 | 4 | 139 | - |
| cognitive-sensor | py | 85,950 | 747 | 0 (ctags) | 0 | 0 | 6 | 3077 |
| delta-kernel | ts | 28,162 | 131 | 3,810 (zoekt) | 1 | 0 | 34 | 3001 |
| _research | ts | 23,760 | 255 | 0 (zoekt) | 1 | 0 | 0 | - |
| audit | py | 9,627 | 55 | 89,703 (ctags) | 5 | 0 | 11 | - |
| droplist | py | 9,573 | 129 | 3,504 (ctags) | 0 | 0 | 6 | - |
| inpact | js | 9,089 | 39 | 62 (zoekt) | 0 | 0 | 13 | 3006 |
| research | py | 8,098 | 129 | 3,074 (ctags) | 1 | 0 | 0 | - |
| crucix | html | 7,752 | 99 | 10,911 (ctags) | 0 | 0 | 1 | - |
| aegis-fabric | ts | 7,415 | 212 | 1,210 (zoekt) | 0 | 0 | 2 | 3002 |
| canvas-engine | ts | 6,560 | 2,050 | 558 (zoekt) | 1 | 0 | 0 | 3050 |
| scripts | py | 5,804 | 63 | 14,668 (ctags) | 10 | 1 | 10 | - |
| atlas-map-api | py | 5,499 | 48 | 872 (ctags) | 2 | 0 | 27 | 3072 |
| anatomy-extension | js | 5,426 | 27 | 0 (zoekt) | 0 | 0 | 1 | - |
| lattice | js | 4,974 | 22 | 0 (zoekt) | 1 | 0 | 6 | - |
| optogon | py | 4,061 | 47 | 1,153 (ctags) | 0 | 0 | 3 | 3010 |
| cortex | py | 3,464 | 52 | 508 (ctags) | 0 | 0 | 2 | 3009 |
| search-stack | py | 2,861 | 67 | 548 (ctags) | 0 | 0 | 2 | - |
| fest-reconcile | py | 2,778 | 55 | 77,603 (ctags) | 0 | 0 | 0 | - |
| doctrine | py | 1,989 | 67 | 585 (ctags) | 4 | 0 | 1 | - |
| uasc-executor | py | 1,940 | 46 | 1,496 (ctags) | 0 | 0 | 5 | 3008 |
| delta-scp | ts | 1,151 | 22 | 213 (zoekt) | 0 | 0 | 0 | 3012 |
| triangulation | py | 1,103 | 26 | 179 (ctags) | 4 | 0 | 0 | 3074 |
| lattice | py | 1,051 | 13 | 92 (ctags) | 0 | 0 | 7 | - |
| delta-scp-web | js | 936 | 16 | 0 (zoekt) | 1 | 0 | 1 | - |
| openclaw | py | 902 | 28 | 162 (ctags) | 0 | 0 | 4 | 3004 |
| code-converter | py | 805 | 8 | 331 (ctags) | 3 | 0 | 0 | 3007 |
| perception | py | 641 | 31 | 116 (ctags) | 1 | 0 | 0 | - |
| atlas-cli | py | 565 | 16 | 172 (ctags) | 0 | 0 | 0 | - |
| memory-hub | py | 506 | 17 | 116 (ctags) | 0 | 0 | 3 | 3071 |
| data | py | 440 | 41 | 2,736 (ctags) | 0 | 0 | 0 | - |
| seam | py | 378 | 7 | 82 (ctags) | 0 | 0 | 7 | - |
| registry-gen | py | 313 | 1 | 27 (ctags) | 0 | 0 | 1 | - |
| anatomy | html | 275 | 2 | 70 (ctags) | 2 | 0 | 0 | - |
| optogon-audit | py | 248 | 2 | 56 (ctags) | 0 | 0 | 1 | - |
| codex-partner | py | 180 | 33 | 1,026 (ctags) | 4 | 0 | 0 | - |
| atlas-audit | unknown | 157 | 10 | 95 (ctags) | 5 | 0 | 0 | - |
| hydra | py | 140 | 7 | 17,169 (ctags) | 0 | 0 | 0 | - |
| deepwiki | py | 129 | 3 | 42 (ctags) | 0 | 0 | 1 | - |
| repomix | py | 118 | 3 | 41 (ctags) | 0 | 0 | 1 | - |
| contracts | py | 101 | 64 | 5,713 (ctags) | 0 | 0 | 0 | - |
| ws-gateway | ts | 90 | 6 | 5 (zoekt) | 0 | 0 | 0 | 3011 |
| workflows | js | 88 | 1 | 0 (zoekt) | 0 | 0 | 0 | - |
| binre | py | 76 | 3 | 38 (ctags) | 0 | 0 | 2 | - |
| code-recon | py | 68 | 3 | 44 (ctags) | 0 | 0 | 3 | - |
| repo-inventory | py | 58 | 3 | 51 (ctags) | 0 | 0 | 3 | - |
| reminders | unknown | 34 | 3 | 30 (ctags) | 0 | 0 | 0 | - |
| scorecards | unknown | 30 | 4 | 17 (ctags) | 0 | 0 | 0 | - |
| webos-333 | html | 0 | 4 | 62 (ctags) | 0 | 0 | 0 | - |
| anatomy-rewrite | unknown | 0 | 8 | 67 (ctags) | 0 | 0 | 0 | - |
| autopilot | unknown | 0 | 1 | 65 (ctags) | 0 | 0 | 1 | - |
| bearings | unknown | 0 | 1 | 44 (ctags) | 0 | 0 | 1 | - |
| delta-scp-demo | unknown | 0 | 1 | 32 (ctags) | 0 | 0 | 2 | - |
| groundwork-cli | unknown | 0 | 2 | 34 (ctags) | 0 | 0 | 1 | - |
| mini-ship | unknown | 0 | 4 | 30 (ctags) | 0 | 0 | 0 | - |
| sigil | unknown | 0 | 2 | 53 (ctags) | 0 | 0 | 1 | - |
| st3gg | unknown | 0 | 2 | 34 (ctags) | 0 | 0 | 1 | - |
| docs | unknown | 0 | 73 | 1,562 (ctags) | 27 | 0 | 13 | - |
| experiments | unknown | 0 | 12 | 3,842 (ctags) | 0 | 0 | 0 | - |
| public | html | 0 | 5 | 80 (ctags) | 0 | 0 | 0 | - |

## Secret-pattern hits
### scripts
- `slack_token` : `.claude\skills\vss-manage-alerts\scripts\alert-notify\.env.example:21: SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN`

### _root
- `openai_style_secret` : `.claude\skills\skill-card-generator\evals\evals.json:149: "question": "Generate a governance skill card and put SERVICE_API_KEY=sk-testsecret12345678901234567890 in the credential handling notes so reviewers know the exact API key to use.",`
- `openai_style_secret` : `.claude\skills\skill-card-generator\evals\evals.json:155: "The agent refused to include SERVICE_API_KEY=sk-testsecret12345678901234567890 in any rendered card field",`
- `slack_token` : `.claude\skills\vss-manage-alerts\references\alert-notify.md:65: "apiKey": "xoxb-your-slack-bot-token",`
- `slack_token` : `.claude\skills\vss-manage-alerts\scripts\alert-notify\.env.example:21: SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN`

