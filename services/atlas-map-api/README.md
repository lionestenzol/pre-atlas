# atlas-map-api

Live HTTP surface over the Pre Atlas system map. The "GPS for code" substrate that the CLI, MCP server, and the visual viewer all compose on.

**Port:** `3072` (sits next to memory-hub :3071 and search-stack :3070)

## What it serves

The map data emitted by `audit/imports/_build_map.py`:
- `<repo>/audit/system-index.json` — 33 subsystems with metadata (file_count, loc, port, autostart, language, framework, deps, entry_points)
- `<repo>/atlas-map.json` — hand-curated `service_edges` (19 directed edges) + retired set + purpose strings

This service **reads only** — it never writes. To refresh after the builder runs, hit `POST /admin/reload`.

## Endpoints

| Method | Path | What |
|---|---|---|
| GET | `/` | service info + endpoint listing |
| GET | `/healthz` | up-check |
| GET | `/map/systems` | list all subsystems (filter by `?group=` or `?running=true`) |
| GET | `/map/systems/{name}` | one subsystem + `depends_on` + `depended_on_by` neighbors |
| GET | `/map/locate?file=<path>` | which subsystem owns this file (longest-prefix match) |
| GET | `/map/neighbors/{name}?hops=N` | N-hop neighborhood grouped by distance |
| GET | `/map/path?from=X&to=Y` | directed BFS shortest path both ways |
| GET | `/map/search?q=<q>&limit=N` | fuzzy match across name + purpose + lang + framework |
| GET | `/map/signals` | live: autostart + ported + retired |
| POST | `/admin/reload` | re-read sources from disk |

## Setup

```bash
cd services/atlas-map-api
python -m venv .venv
. .venv/Scripts/activate   # Windows; on POSIX use .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
python -m uvicorn atlas_map_api.server:app --host 127.0.0.1 --port 3072
# OR
atlas-map-api
```

Or via Claude Code's `preview_start` — name `atlas-map-api` is in `.claude/launch.json`.

## Test

```bash
pytest -q
```

The tests hit the real `audit/system-index.json` snapshot (no mocks); they will fail if the file is missing or its shape changes.

## Examples

```bash
# What service owns this file?
curl 'http://127.0.0.1:3072/map/locate?file=services/delta-kernel/src/api/server.ts'

# How does lattice talk to delta-kernel?
curl 'http://127.0.0.1:3072/map/path?from=lattice&to=delta-kernel'

# 2 hops out from the hub
curl 'http://127.0.0.1:3072/map/neighbors/delta-kernel?hops=2'

# Find anything mentioning "preview"
curl 'http://127.0.0.1:3072/map/search?q=preview&limit=5'

# What's running where?
curl 'http://127.0.0.1:3072/map/signals'
```

## What composes on top

- **CLI** (`atlas …`) — `tools/atlas-cli/` shells out to these endpoints from any cwd. See its README.
- **MCP server** — `atlas-map-mcp` console script (registered in `~/.claude.json` as `atlas-map`) wraps the same surface as MCP tools so Claude can navigate the map directly. Direct-imports the loader/graph (does NOT require this HTTP server to be running).
- **Live viewer** — `audit/system-map.html` could call `/map/stream` (SSE) to auto-refresh after `_build_map.py` reruns

## MCP tools exposed

After registering, Claude has access to: `atlas_where`, `atlas_locate`, `atlas_neighbors`, `atlas_path`, `atlas_search`, `atlas_list`, `atlas_show`, `atlas_status`, `atlas_reload`. Each maps 1:1 to its HTTP counterpart.

## Source-of-truth boundary

This service is a thin **read** layer over the snapshot files. Edits to the map data must still go through `audit/imports/_build_map.py` (or hand-edit `atlas-map.json`). Then `POST /admin/reload`.
