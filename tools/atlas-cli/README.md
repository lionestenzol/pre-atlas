# atlas-cli

GPS for Pre Atlas — query the system map from any cwd.

A thin Python CLI over [`atlas-map-api`](../../services/atlas-map-api) (`:3072`). The API does all the work; this just gives you `atlas <verb>` in your shell so the same map that powers the visual viewer is one command away.

## Install

```bash
cd tools/atlas-cli
python -m venv .venv
. .venv/Scripts/activate     # Windows; on POSIX use .venv/bin/activate
pip install -e ".[dev]"
```

The `atlas` console script lands on PATH inside the venv. Add the venv's `Scripts/` to PATH (or alias it) if you want it global.

## Requires

- `atlas-map-api` running on `:3072`. Start it via `preview_start atlas-map-api` or run it manually from `services/atlas-map-api`.
- Override the base URL with `--api http://host:port` or `ATLAS_API_URL=...`.

## Subcommands

| Command | Purpose |
|---|---|
| `atlas where` | Which subsystem owns the current cwd? |
| `atlas locate <file>` | Which subsystem owns the given path? (abs / cwd-rel / repo-rel all work) |
| `atlas neighbors <name> [-n N]` | N-hop dependency neighborhood |
| `atlas path <from> <to>` | Shortest directed dependency path (both directions) |
| `atlas search <q> [-l N]` | Fuzzy match across name + purpose + language + framework |
| `atlas list [-g group] [--running]` | List subsystems, optionally filtered |
| `atlas show <name>` | Detail card with depends_on / depended_on_by |
| `atlas status` | Live signals: ports + autostart + retired |
| `atlas reload` | Re-read `system-index.json` + `atlas-map.json` from disk |
| `atlas open [name]` | Open `system-map.html` in your browser (optionally focused) |

## Global flags

- `--json` — emit JSON instead of a rich table (pipe-friendly).
- `--api URL` — override base URL (default `http://127.0.0.1:3072` or `$ATLAS_API_URL`).

## Examples

```bash
# Which service am I in?
$ cd services/delta-kernel/src
$ atlas where
delta-kernel  (services/delta-kernel/src)

# Where does this file live?
$ atlas locate services/cognitive-sensor/atlas_query.py
cognitive-sensor  <- services/cognitive-sensor/atlas_query.py

# Who talks to whom?
$ atlas neighbors delta-kernel -n 2

# Trace the wire
$ atlas path lattice delta-kernel
→ lattice → delta-kernel

# Quick search
$ atlas search preview --limit 3

# Snapshot of running ports
$ atlas status

# Open the viewer focused on a node
$ atlas open cognitive-sensor

# Pipe-friendly
$ atlas --json list --group services | jq '.items[].name'
```

## Test

```bash
pytest -q
```

Tests hit the live API on `:3072` and skip cleanly if it isn't running.

## How it composes

```
   audit/_build_map.py  ──writes──>  audit/system-index.json + atlas-map.json
                                          │
                              read-only ↓
   atlas-map-api (:3072)  ─── HTTP ────────────┐
                                               ├── audit/system-map.html  (visual)
                                               ├── atlas-cli              (terminal)
                                               └── MCP server             (Claude tools)
```

Every consumer reads the same snapshot. Edits go through `_build_map.py`, then `atlas reload`.
