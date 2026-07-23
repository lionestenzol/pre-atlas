# Pre Atlas — Surfaces, CLIs, UIs, TS/HTML inventory
_Generated 2026-06-20. Source tree only (node_modules, .venv, builds, worktrees, fuzz-corpus, generated dirs excluded)._

## A. Served surfaces (running UIs + APIs, from `.claude/launch.json`)

### Web UIs (open in a browser)
| port | name | serves |
|---|---|---|
| 3000 | mosaic-dashboard | Next.js dashboard (legacy) |
| 3006 | inpact | inPACT daily-flow UI (`apps/inpact`) |
| 3011 | lattice | lattice viewer (`apps/lattice/index.html`) |
| 3050 | canvas-engine | URL→React clone viewer |
| 3074 | droplist-ui | droplist UI (`services/droplist/ui`) — added this session |
| 5173 | delta-web | delta-kernel web (Vite) |
| 8888 | atlas-shell | repo root static |
| 8889 | cycleboard | `services/cognitive-sensor/cycleboard` |
| 8890 | aegis-landing | aegis landing |
| 8891 | cortex-dashboard | `services/cortex` static |
| 8892 | inpact-site-legacy | legacy inPACT site (Desktop) |
| 8893 | thread-cards | `services/cognitive-sensor` static (thread_cards.html) |
| 8894 | anatomy | `anatomy/` static |
| 8895 | tour-test | openscreen lift test |
| 8896 | anatomy-calibration | `tools/anatomy-extension` |
| 8897 | audit-map | `audit/` static (system-map.html) |

### API services (HTTP/MCP, no human UI)
| port | name |
|---|---|
| 3001 | delta-api (delta-kernel) |
| 3002 | aegis-api (aegis-fabric) |
| 3004 | openclaw · 3005 mosaic-orch · 3007 code-converter · 3008 uasc · 3009 cortex |
| 3010 | optogon · 3070 search-stack · 3071 memory-hub · 3072 atlas-map-api · 3073 droplist-api |
| 5000 | ai-exec-pipeline · 8765 triage-server |

## B. CLIs

| CLI | path | what |
|---|---|---|
| `atlas` (GPS) | `tools/atlas-cli/src/atlas_cli/main.py` | system-map CLI (where/locate/neighbors/path/search/list/show/status/reload/open) |
| `atlas` (human) | `services/delta-kernel/src/cli/atlas.ts` | CycleBoard human CLI (20/21 screens) |
| `atlas-ai` | `services/delta-kernel/src/cli/atlas-ai.ts` | JSON-native CLI for AI agents |
| `at` (triage) | `services/cognitive-sensor/atlas_triage_cli.py` | triage pipeline dispatcher |
| atlas_cli | `services/cognitive-sensor/atlas_cli.py` | cognitive-sensor CLI |
| cycleboard | `services/cognitive-sensor/cycleboard/cli.ts` | older CycleBoard CLI subset |
| droplist `drop` | `services/droplist/droplist/cli.py` | intake CLI (drop/recent/show/morning/review/brief/graph/ship) |
| fuzz | `services/cognitive-sensor/fuzz/cli.py` | fuzz harness |
| uasc-m2m | `research/uasc-m2m/reference-implementation/mvp/cli.py` | reference impl |

Console-script entry points also in: atlas-map-api, delta-kernel, droplist, memory-hub, mirofish, mosaic-orchestrator, openclaw, search-stack, atlas-cli.

## C. HTML surfaces (hand-authored)

### apps/
- inpact: `index.html`, `today.html`, `onboarding.html`, `followup.html`, `method.html`, `brand/{faq,features,landing,logo}.html`, `onboarding/{cta,pricing}.html`
- lattice: `index.html` (workflow viewer), `system-map.html` (GPS map)
- code-converter: `index.html`
- ai-exec-pipeline: `static/index.html`
- webos-333: `web-os-simulator.html`

### services/
- cognitive-sensor: `atlas_explorer.html`, `atlas_galaxy.html`, `atlas_template.html`, `blueprint.html`, `cognitive_atlas.html`, `cognitive_map.html`, `control_panel.html`, `cycleboard/index.html`, `dashboard.html`, `docs_viewer.html`, `idea_dashboard.html`, `thread_cards.html`
- delta-kernel: `src/ui/control.html`, `src/ui/timeline.html`, `web/index.html`, `src/core/{audio,camera,voice}-live-test.html`
- droplist: `ui/chain.html`, `ui/line.html`
- cortex: `dashboard.html`
- aegis-fabric: `landing/index.html`, `src/ui/dashboard.html`
- canvas-engine: `sandbox-template/index.html`

### tools/ + top-level
- tools/anatomy-extension: `popup.html`, `calibration/index.html`
- root: `atlas_boot.html`, `system-map.html`, `system-tour.html`, `pre-atlas-pattern-map.html`, `anatomy/today.html`, `data/consulting/landing.html`

## D. TypeScript (.ts) — 227 files (excl .d.ts, node_modules)
| count | area |
|---|---|
| 83 | services/aegis-fabric |
| 65 | services/delta-kernel |
| 57 | services/canvas-engine |
| 10 | services/mosaic-dashboard |
| 7 | apps/blueprint-generator |
| 2 | apps/canvas-demo |
| 1 each | services/ws-gateway, services/cognitive-sensor, apps/inpact |

## Notes
- Generated/excluded: `services/cognitive-sensor/fuzz-corpus/*` (~45 html), `services/canvas-engine/.canvas-sessions/*` (~18 html), `services/mosaic-dashboard/.next/*`, `apps/blueprint-generator/out/*`, `_archive/*`. Full raw count incl. generated = 112 html.
- Port drift exists in `system-index.json` (e.g. ws-gateway/inpact both :3006, aegis/triangulation both :3010, droplist/memory-hub :3071) — task chip open to fix.
