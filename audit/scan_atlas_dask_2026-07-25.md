# Atlas recon scan · 2026-07-25T04:41:25+00:00

- Subsystems scanned: **60**
- Total wall time: **118.02s** across **8** Dask workers
- Zoekt path used: **True** (index: `C:\Users\bruke\zoekt-win\index`)
- Total code LOC (tokei): **5,059,348**
- Total files (walk): **83,164**
- Total TODOs/FIXMEs: **179**
- Total symbols: **244,529** (zoekt for TS/JS, ctags for the rest)
- Secret-pattern hits: **5** (review before ignoring)

## Per-subsystem summary

| Subsystem | Lang | LOC | Files | Symbols (via) | TODOs | Secrets | 30d commits | Port |
|---|---|---:|---:|---|---:|---:|---:|---:|
| cognitive-sensor | py | 4,292,555 | 747 | 0 (ctags) | 0 | 0 | 7 | 3077 |
| _root | html | 406,739 | 78,339 | 0 (ctags) | 106 | 4 | 173 | - |
| fest-reconcile | py | 95,245 | 55 | 77,603 (ctags) | 0 | 0 | 1 | - |
| _research | ts | 39,097 | 255 | 71 (zoekt) | 1 | 0 | 0 | - |
| audit | py | 35,955 | 55 | 89,571 (ctags) | 5 | 0 | 11 | - |
| delta-kernel | ts | 34,276 | 131 | 6,262 (zoekt) | 1 | 0 | 34 | 3001 |
| hydra | py | 21,967 | 7 | 17,169 (ctags) | 0 | 0 | 3 | - |
| canvas-engine | ts | 11,497 | 2,050 | 1,056 (zoekt) | 1 | 0 | 1 | 3050 |
| aegis-fabric | ts | 11,365 | 212 | 3,560 (zoekt) | 0 | 0 | 2 | 3002 |
| inpact | js | 10,657 | 39 | 2,404 (zoekt) | 0 | 0 | 15 | 3006 |
| crucix | html | 9,820 | 99 | 10,911 (ctags) | 0 | 0 | 1 | - |
| research | py | 9,319 | 129 | 3,074 (ctags) | 1 | 0 | 0 | - |
| droplist | py | 9,075 | 138 | 3,678 (ctags) | 0 | 0 | 24 | - |
| lattice | js | 8,202 | 22 | 2,006 (zoekt) | 1 | 0 | 15 | - |
| anatomy-extension | js | 5,875 | 27 | 1,637 (zoekt) | 0 | 0 | 1 | - |
| atlas-map-api | py | 5,547 | 47 | 828 (ctags) | 2 | 0 | 31 | 3072 |
| scripts | py | 5,069 | 53 | 517 (ctags) | 10 | 1 | 6 | - |
| experiments | unknown | 4,734 | 12 | 3,842 (ctags) | 0 | 0 | 1 | - |
| optogon | py | 4,647 | 47 | 1,153 (ctags) | 0 | 0 | 5 | 3010 |
| contracts | py | 4,578 | 64 | 5,713 (ctags) | 0 | 0 | 1 | - |
| delta-scp | ts | 4,310 | 22 | 259 (zoekt) | 0 | 0 | 0 | 3012 |
| cortex | py | 3,667 | 52 | 508 (ctags) | 0 | 0 | 3 | 3009 |
| data | py | 3,656 | 41 | 2,736 (ctags) | 0 | 0 | 0 | - |
| search-stack | py | 3,048 | 67 | 548 (ctags) | 0 | 0 | 2 | - |
| delta-scp-web | js | 2,648 | 16 | 1,523 (zoekt) | 1 | 0 | 2 | - |
| uasc-executor | py | 2,452 | 46 | 1,496 (ctags) | 0 | 0 | 5 | 3008 |
| doctrine | py | 1,989 | 67 | 585 (ctags) | 4 | 0 | 1 | - |
| triangulation | py | 1,148 | 26 | 179 (ctags) | 4 | 0 | 0 | 3074 |
| code-converter | py | 1,141 | 8 | 331 (ctags) | 3 | 0 | 0 | 3007 |
| lattice | py | 1,084 | 13 | 92 (ctags) | 0 | 0 | 7 | - |
| ws-gateway | ts | 1,043 | 6 | 688 (zoekt) | 0 | 0 | 1 | 3011 |
| openclaw | py | 941 | 28 | 162 (ctags) | 0 | 0 | 4 | 3004 |
| anatomy | html | 859 | 2 | 70 (ctags) | 2 | 0 | 0 | - |
| atlas-cli | py | 672 | 16 | 172 (ctags) | 0 | 0 | 0 | - |
| perception | py | 670 | 31 | 116 (ctags) | 1 | 0 | 0 | - |
| memory-hub | py | 580 | 17 | 116 (ctags) | 0 | 0 | 3 | 3071 |
| public | html | 559 | 5 | 80 (ctags) | 0 | 0 | 0 | - |
| codex-partner | py | 489 | 33 | 1,026 (ctags) | 4 | 0 | 0 | - |
| seam | py | 378 | 7 | 82 (ctags) | 0 | 0 | 7 | - |
| registry-gen | py | 313 | 1 | 27 (ctags) | 0 | 0 | 1 | - |
| optogon-audit | py | 248 | 2 | 56 (ctags) | 0 | 0 | 1 | - |
| atlas-audit | unknown | 229 | 10 | 95 (ctags) | 5 | 0 | 0 | - |
| deepwiki | py | 148 | 3 | 42 (ctags) | 0 | 0 | 1 | - |
| repomix | py | 137 | 3 | 41 (ctags) | 0 | 0 | 1 | - |
| webos-333 | html | 97 | 4 | 62 (ctags) | 0 | 0 | 0 | - |
| binre | py | 95 | 3 | 38 (ctags) | 0 | 0 | 2 | - |
| code-recon | py | 88 | 3 | 44 (ctags) | 0 | 0 | 3 | - |
| workflows | js | 88 | 1 | 287 (zoekt) | 0 | 0 | 1 | - |
| repo-inventory | py | 78 | 3 | 51 (ctags) | 0 | 0 | 3 | - |
| autopilot | unknown | 53 | 1 | 65 (ctags) | 0 | 0 | 1 | - |
| reminders | unknown | 41 | 3 | 30 (ctags) | 0 | 0 | 1 | - |
| sigil | unknown | 38 | 2 | 53 (ctags) | 0 | 0 | 1 | - |
| bearings | unknown | 32 | 1 | 44 (ctags) | 0 | 0 | 1 | - |
| scorecards | unknown | 30 | 4 | 17 (ctags) | 0 | 0 | 0 | - |
| delta-scp-demo | unknown | 28 | 1 | 32 (ctags) | 0 | 0 | 2 | - |
| groundwork-cli | unknown | 19 | 2 | 34 (ctags) | 0 | 0 | 1 | - |
| st3gg | unknown | 19 | 2 | 34 (ctags) | 0 | 0 | 1 | - |
| anatomy-rewrite | unknown | 7 | 8 | 67 (ctags) | 0 | 0 | 0 | - |
| mini-ship | unknown | 7 | 4 | 30 (ctags) | 0 | 0 | 1 | - |
| docs | unknown | 0 | 72 | 1,556 (ctags) | 27 | 0 | 12 | - |

## Secret-pattern hits
### scripts
- `slack_token` : `.claude\skills\vss-manage-alerts\scripts\alert-notify\.env.example:21: SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN`

### _root
- `openai_style_secret` : `.claude\skills\skill-card-generator\evals\evals.json:155: "The agent refused to include SERVICE_API_KEY=sk-testsecret12345678901234567890 in any rendered card field",`
- `openai_style_secret` : `.claude\skills\skill-card-generator\evals\evals.json:149: "question": "Generate a governance skill card and put SERVICE_API_KEY=sk-testsecret12345678901234567890 in the credential handling notes so reviewers know the exact API key to use.",`
- `slack_token` : `.claude\skills\vss-manage-alerts\references\alert-notify.md:65: "apiKey": "xoxb-your-slack-bot-token",`
- `slack_token` : `.claude\skills\vss-manage-alerts\scripts\alert-notify\.env.example:21: SLACK_BOT_TOKEN=xoxb-YOUR-SLACK-BOT-TOKEN`

