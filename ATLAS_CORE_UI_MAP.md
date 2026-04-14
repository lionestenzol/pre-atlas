# ATLAS CORE UI MAP

> Generated: 2026-02-22 | Pre Atlas v1.0

---

## Architecture Overview

```
                          +===========================+
                          |      ATLAS CORE SHELL     |
                          |     atlas_boot.html       |
                          |  (Root Orchestrator/907L)  |
                          +============+==============+
                                       |
            +-----------+--------------+--------------+-----------+
            |           |              |              |           |
     [CycleBoard]  [Control]     [Telemetry]    [Desktop]   [API Layer]
      Tab iframe    Tab iframe   Right panel    Fullscreen   localhost:3001
            |           |              |              |           |
            v           v              v              v           v
  +---------+--+ +------+------+ +----+----+ +-------+-------+ +-+----------+
  | cycleboard/| | control_    | | dash-   | | web-os-       | | delta-     |
  | index.html | | panel.html  | | board   | | simulator     | | kernel     |
  | (161L)     | | (201L)      | | .html   | | .html         | | Express    |
  | 10 JS mods | |             | | (58L)   | | (3442L)       | | :3001      |
  +-----+------+ +------+------+ +---------+ +---------------+ +--+---------+
        |                |                                         |
   cognitive_       cognitive_                              +------+------+
   state.json       state.json                              |             |
                                                       control.html  timeline.html
                                                        (96L)          (289L)
```

---

## 1. File Inventory (20 Files)

### Tier 1: Active Core (6 files)

| File | Lines | Role | Location |
|------|-------|------|----------|
| `atlas_boot.html` | 907 | Root orchestrator shell | `/` |
| `cycleboard/index.html` | 161 | CycleBoard daily planner (modular) | `services/cognitive-sensor/cycleboard/` |
| `control_panel.html` | 201 | Cognitive system control panel | `services/cognitive-sensor/` |
| `dashboard.html` | 58 | Cognitive telemetry dashboard | `services/cognitive-sensor/` |
| `idea_dashboard.html` | 493 | Idea intelligence dashboard | `services/cognitive-sensor/` |
| `web-os-simulator.html` | 3,442 | Browser-based OS simulator | `apps/webos-333/` |

### Tier 2: Delta-Kernel UI (4 files)

| File | Lines | Role | Location |
|------|-------|------|----------|
| `control.html` | 96 | Work queue status panel | `services/delta-kernel/src/ui/` |
| `timeline.html` | 289 | System event timeline viewer | `services/delta-kernel/src/ui/` |
| `web/index.html` | 13 | Vite/React SPA shell | `services/delta-kernel/web/` |

### Tier 3: Hardware Test Pages (3 files)

| File | Lines | Role | Location |
|------|-------|------|----------|
| `camera-live-test.html` | 444 | Delta-state camera streaming | `services/delta-kernel/src/core/` |
| `audio-live-test.html` | 410 | Delta-state audio streaming | `services/delta-kernel/src/core/` |
| `voice-live-test.html` | 655 | LPC/Codec2 voice codec test | `services/delta-kernel/src/core/` |

### Tier 4: Generated / Template (3 files)

| File | Lines | Role | Location |
|------|-------|------|----------|
| `atlas_template.html` | 612 | Python template (Plotly + Sigma.js) | `services/cognitive-sensor/` |
| `cognitive_atlas.html` | 612 | **GENERATED** -- gitignored | `services/cognitive-sensor/` |
| `cognitive_map.html` | 218 | **GENERATED** -- gitignored (378KB) | `services/cognitive-sensor/` |

### Tier 5: Standalone / Apps (3 files)

| File | Lines | Role | Location |
|------|-------|------|----------|
| `pre-atlas-pattern-map.html` | 1,167 | Static behavioral pattern report | `/` |
| `out/index.html` | 1 | Next.js Blueprint Generator | `apps/blueprint-generator/out/` |
| `out/404.html` | 1 | Next.js 404 page | `apps/blueprint-generator/out/` |

### Archived (3 files -- `_archive/`)

| File | Lines | Status |
|------|-------|--------|
| `cycleboard_app3.html` | 5,554 | Deprecated monolithic CycleBoard |
| `cycleboard_app3_original.html` | 4,394 | Predecessor to app3 |
| `cycleboard_cognitive.html` | 5,615 | Monolithic + cognitive banner |

---

## 2. Iframe Embedding Hierarchy

```
atlas_boot.html
 |
 |-- [TAB: CycleBoard] -----> cycleboard/index.html
 |     |                          |-- js/state.js
 |     |                          |-- js/validator.js
 |     |                          |-- js/ui.js
 |     |                          |-- js/helpers.js
 |     |                          |-- js/screens.js
 |     |                          |-- js/functions.js
 |     |                          |-- js/cognitive.js ---> fetch(cognitive_state.json)
 |     |                          |-- js/ai-context.js
 |     |                          |-- js/ai-actions.js
 |     |                          |-- js/app.js
 |     |                          `-- css/styles.css
 |     |
 |     `-- cognitive.js window.open() --> control_panel.html
 |
 |-- [TAB: Control Panel] --> control_panel.html
 |     |-- window.open() --> dashboard.html
 |     `-- window.open() --> cycleboard/index.html
 |
 |-- [RIGHT PANEL: Telemetry] --> dashboard.html
 |
 |-- [MODAL: Control] ------> control_panel.html
 |
 `-- [OVERLAY: Desktop] ----> web-os-simulator.html
```

---

## 3. Data Flow Architecture

```
+=====================+         +========================+
|   PYTHON PIPELINE   |         |    DELTA-KERNEL API    |
|   (cognitive-sensor)|         |    localhost:3001      |
+==========+==========+         +===========+============+
           |                                |
    [writes JSON files]             [REST endpoints]
           |                                |
    +------+------+              +----------+-----------+
    |             |              |          |           |
cognitive_   idea_          /api/state  /api/work   /api/timeline
state.json   registry       /unified    /status     ?limit&type
    |        .json          /api/law    /history    /stats
    |             |         /api/daemon
    |             |         /status
    v             v              |
+---+---+  +-----+------+       v
|control|  |idea_dash-  | +-----+----------+
|_panel |  |board.html  | | atlas_boot.html|
|.html  |  +------------+ | control.html   |
+---+---+                  | timeline.html  |
    |                      +----------------+
    v
cycleboard/
index.html
(via cognitive.js)
```

### JSON File Dependencies

| Consumer | JSON File | Written By |
|----------|-----------|------------|
| `control_panel.html` | `cognitive_state.json` | Python pipeline |
| `cycleboard/index.html` | `cognitive_state.json` | Python pipeline |
| `idea_dashboard.html` | `idea_registry.json` | Python pipeline |
| `atlas_template.html` | `__DATA_PAYLOAD__` (inline) | `build_cognitive_atlas.py` |

### API Endpoint Surface

| File | Endpoint | Method | Polling |
|------|----------|--------|---------|
| `atlas_boot.html` | `/api/state/unified` | GET | 30s |
| `atlas_boot.html` | `/api/daemon/status` | GET | 30s |
| `atlas_boot.html` | `/api/law/acknowledge` | POST | on-click |
| `atlas_boot.html` | `/api/law/archive` | POST | on-click |
| `atlas_boot.html` | `/api/law/refresh` | POST | on-click |
| `control.html` | `/api/work/status` | GET | 5s |
| `control.html` | `/api/work/history` | GET | on-load |
| `timeline.html` | `/api/timeline` | GET | 10s |
| `timeline.html` | `/api/timeline/stats` | GET | 10s |

---

## 4. Technology Clusters

```
CLUSTER A: Tailwind + Font Awesome (Modern UI)
  |- cycleboard/index.html    [TW 3.4.1 + FA 6.4.0]
  |- control_panel.html       [TW 3.4.1 + FA 6.4.0]
  `- idea_dashboard.html      [TW 3.4.1 + FA 6.4.0]

CLUSTER B: Plotly + Sigma.js (Data Visualization)
  |- atlas_template.html      [Plotly 2.27.0 + Sigma 2.4.0 + Graphology 0.25.4]
  |- cognitive_atlas.html     [same -- generated from template]
  `- cognitive_map.html       [Plotly 2.27.0 only]

CLUSTER C: Vanilla Dark Terminal (System UI)
  |- atlas_boot.html          [custom CSS, dark theme]
  |- control.html             [inline CSS, dark terminal]
  |- timeline.html            [inline CSS, dark terminal]
  `- dashboard.html           [inline CSS, light theme]

CLUSTER D: Green Terminal (Hardware Tests)
  |- camera-live-test.html    [green-on-black, WebRTC]
  |- audio-live-test.html     [green-on-black, Web Audio]
  `- voice-live-test.html     [green-on-black, LPC/Codec2]

CLUSTER E: Framework SPAs
  |- delta-kernel/web/index.html         [Vite + React + TypeScript]
  `- blueprint-generator/out/index.html  [Next.js static export]

CLUSTER F: Standalone Rich Document
  `- pre-atlas-pattern-map.html          [monospace dark, CSS vars]

CLUSTER G: Desktop OS Simulation
  `- web-os-simulator.html               [CSS vars, 3 themes, virtual FS]
```

---

## 5. localStorage Key Map

| Key | Owner | Purpose |
|-----|-------|---------|
| `cycleboard-state` | `cycleboard/index.html` | Full app state (tasks, journal, goals) |
| `milestones-{YYYY-MM-DD}` | `cycleboard/index.html` | Daily milestone completions |
| `cycleboard-export-count` | `cycleboard/index.html` | Export counter |
| `cycleboard-last-export` | `cycleboard/index.html` | Timestamp of last export |
| `cycleboard-last-import` | `cycleboard/index.html` | Timestamp of last import |
| `webos-filesystem` | `web-os-simulator.html` | Virtual filesystem data |
| `webos-username` | `web-os-simulator.html` | User display name |
| `webos-theme` | `web-os-simulator.html` | Theme selection (default/xp/dark) |
| `webos-wallpaper` | `web-os-simulator.html` | Custom wallpaper URL |
| `webos-sound` | `web-os-simulator.html` | Sound enabled/disabled |

---

## 6. Cross-Reference Graph

```
                    atlas_boot.html
                   /    |    \     \
                  /     |     \     \
                 v      v      v     v
  cycleboard/ control_ dash-  web-os-
  index.html  panel    board  simulator
       |         |  \
       |         |   v
       |         | dashboard.html
       v         v
  control_    cycleboard/
  panel.html  index.html

  timeline.html <---> control.html (delta-kernel pair)

  ORPHANED (no inbound references from HTML):
    - pre-atlas-pattern-map.html
    - idea_dashboard.html
    - cognitive_atlas.html (generated)
    - cognitive_map.html (generated)
    - camera-live-test.html
    - audio-live-test.html
    - voice-live-test.html
    - delta-kernel/web/index.html (served by Vite)
    - blueprint-generator/out/index.html (served by Next.js)
    - _archive/*.html (3 files, deprecated)
```

---

## 7. Accessibility Status

| File | ARIA | Semantic HTML | Score |
|------|------|---------------|-------|
| `cycleboard/index.html` | `role`, `aria-label`, `aria-expanded`, `aria-controls`, `aria-hidden`, `aria-live` | `<header>`, `<nav>`, `<main>`, `<aside>` | **A** |
| All other 19 files | None | None | **F** |

The CycleBoard modular refactor is the **only** file with accessibility support.

---

## 8. Build Pipeline

```
COGNITIVE ATLAS PIPELINE:
  build_cognitive_atlas.py
    -> atlas_projection.py (UMAP + HDBSCAN)
    -> atlas_render.py
    -> fills atlas_template.html
    -> outputs cognitive_atlas.html (gitignored)

COGNITIVE MAP PIPELINE:
  build_cognitive_map.py
    -> outputs cognitive_map.html (gitignored, 378KB)

DELTA-KERNEL SPA:
  npm run dev (Vite)
    -> serves delta-kernel/web/index.html
    -> hot-reloads src/main.tsx

BLUEPRINT GENERATOR:
  npm run build (Next.js)
    -> outputs apps/blueprint-generator/out/index.html
```

---

## 9. CDN Dependencies

| Library | Version | CDN URL | Files |
|---------|---------|---------|-------|
| Tailwind CSS | 3.4.1 | `cdn.tailwindcss.com/3.4.1` | 3 active files |
| Font Awesome | 6.4.0 | `cdnjs.cloudflare.com/.../font-awesome/6.4.0` | 3 active files |
| Plotly | 2.27.0 | `cdn.plot.ly/plotly-2.27.0.min.js` | 3 viz files |
| Graphology | 0.25.4 | `cdnjs.cloudflare.com/.../graphology/0.25.4` | 2 atlas files |
| Sigma.js | 2.4.0 | `cdnjs.cloudflare.com/.../sigma.js/2.4.0` | 2 atlas files |

---

## 10. System Entry Points

```
PRIMARY:   atlas_boot.html           (open in browser -- full system cockpit)
                                      Requires: delta-kernel running on :3001

STANDALONE ACCESS:
  - cycleboard/index.html             (daily planner, works offline via JSON)
  - control_panel.html                (system status, needs cognitive_state.json)
  - idea_dashboard.html               (idea tracker, needs idea_registry.json)
  - web-os-simulator.html             (desktop OS, fully self-contained)

DEV SERVERS:
  - localhost:3001                     (delta-kernel Express + static UI)
  - localhost:5173                     (Vite React SPA dev server)
  - localhost:3000                     (Next.js Blueprint Generator dev)

GENERATED (rebuild required):
  - cognitive_atlas.html               (python build_cognitive_atlas.py)
  - cognitive_map.html                 (python build_cognitive_map.py)
```

---

*Total: 20 project HTML files | ~24,800 lines | 5 CDN dependencies | 9 API endpoints | 10 localStorage keys*
