# fest-tools

Python wrapper + MCP server for the `fest` CLI.

## Layout

- `fest_py/` — Python package (`FestClient`) that shells out to `fest --json`
- `mcp_server/` — MCP-over-stdio server exposing fest tools to Claude

## Install

```bash
cd services/fest-tools
pip install -e .
```

Requires `fest.exe` on PATH (installed at `C:\Users\bruke\bin\fest.exe`).

## Use — Python

```python
from fest_py import FestClient
c = FestClient()
c.list("active")               # [Festival, ...]
c.progress("atlas-pivot-AP0001")
c.next("atlas-pivot-AP0001")
c.promote("cycleboard-wiring-CW0001")
```

## Use — MCP

Register in `~/.claude.json` under `mcpServers`:

```json
"fest": {
  "command": "python",
  "args": ["-m", "mcp_server.server"],
  "cwd": "C:/Users/bruke/Pre Atlas/services/fest-tools"
}
```

Tools exposed:
- `fest_list(status?, include_dungeon?)`
- `fest_progress(festival)`
- `fest_next(festival)`
- `fest_status()`
- `fest_promote(festival, dungeon?)`
- `fest_task_complete(festival, task_id)`

## Known JSON gap

`fest task`, `fest state`, `fest chain` do not accept `--json` yet. Those methods
in `client.py` fall back to text output. Upstream PR to fest to add `--json`
would remove the last text-parsing surface.
