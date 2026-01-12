# Scripts

Automation scripts for running the Pre Atlas stack.

---

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `run_all.ps1` | **Full stack launcher** - starts everything |
| `run_delta_api.ps1` | Start Delta Kernel API only |
| `run_cognitive.ps1` | Run cognitive sensor refresh only |
| `run_delta_cli.ps1` | Start Delta CLI interface |

---

## run_all.ps1 (Recommended)

The primary automation script that runs the complete 4-step pipeline:

```powershell
.\scripts\run_all.ps1
```

**What it does:**

1. **[1/4] Start Delta API** - Launches API server in new terminal window
2. **[2/4] Run Cognitive Sensor** - Executes `refresh.py` pipeline
3. **[3/4] Build Daily Projection** - Creates `today.json` artifact
4. **[4/4] Push to Delta** - POSTs cognitive data to Delta API

**Outputs:**

| Output | Location |
|--------|----------|
| Delta API | `http://localhost:3001` |
| Delta Data | `.delta-fabric/` |
| Daily Projection | `data/projections/today.json` |
| Cognitive State | `services/cognitive-sensor/cognitive_state.json` |
| Dashboard | `services/cognitive-sensor/dashboard.html` |
| CycleBoard | `services/cognitive-sensor/cycleboard_app3.html` |

---

## run_delta_api.ps1

Start only the Delta Kernel API server:

```powershell
.\scripts\run_delta_api.ps1
```

- Runs on `http://localhost:3001`
- Uses `.delta-fabric/` for data storage
- Set `DELTA_DATA_DIR` env var to customize

---

## run_cognitive.ps1

Run only the cognitive sensor refresh pipeline:

```powershell
.\scripts\run_cognitive.ps1
```

- Executes `services/cognitive-sensor/refresh.py`
- Generates dashboard, directive, and payload
- Does NOT push to Delta API

---

## run_delta_cli.ps1

Start the Delta CLI terminal interface:

```powershell
.\scripts\run_delta_cli.ps1
```

- Interactive terminal UI for task management
- Keyboard-driven interface

---

## Daily Workflow

**Morning routine:**

```powershell
# From repo root:
.\scripts\run_all.ps1
```

This refreshes all cognitive metrics and starts the governance system.

---

## Data Flow

```
run_all.ps1
    │
    ├──► Delta API (port 3001)
    │
    ├──► refresh.py
    │       ├──► loops.py (detect open loops)
    │       ├──► completion_stats.py (closure metrics)
    │       ├──► export_cognitive_state.py
    │       ├──► route_today.py
    │       └──► export_daily_payload.py
    │
    ├──► build_projection.py
    │       └──► data/projections/today.json
    │
    └──► push_to_delta.py
            └──► POST /api/ingest/cognitive
```

---

## Requirements

- **PowerShell** (Windows)
- **Python 3.x** with dependencies from `services/cognitive-sensor/requirements.txt`
- **Node.js** for Delta Kernel

---

## Troubleshooting

### Delta API won't start
- Check if port 3001 is in use: `netstat -an | findstr 3001`
- Ensure `npm install` was run in `services/delta-kernel/`

### Cognitive refresh fails
- Ensure `results.db` exists in `services/cognitive-sensor/`
- Check Python dependencies: `pip install -r requirements.txt`

### Push to Delta fails
- Ensure Delta API is running on port 3001
- Check API health: `curl http://localhost:3001/api/state`

---

*Part of the Pre Atlas personal operating system.*
