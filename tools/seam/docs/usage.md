# Seam usage

Three ways to call the seam, then a reference for each of the 7 surfaces.

## The two switches

The gateway is fail-closed. Set these before calling (the `seam` CLI sets CLI for you; use
`--writes` for the write switch):

| Env var | Turns on |
|---|---|
| `DESCRIBE_GATEWAY_CLI=1` | the CLI tools (always needed) |
| `DESCRIBE_GATEWAY_WRITES=1` | file-writing capabilities (`gw index`, `sigil pack`) |

## Path 1 — the `seam` CLI (recommended; no server, no Claude)

`seam` is on PATH (`~/bin/seam` bash/WSL, `~/bin/seam.cmd` PowerShell/cmd). It drives the gateway
in-process.

```bash
seam list                                   # every registered surface + capability
seam call <surface> <capability> k=v ...    # call one tool -> print its Receipt
seam perceive <repo> [--writes]             # inventory + orient + index -> a manifest
```

Flags (place them after the subcommand): `--json` (machine manifest), `--writes` (allow writes),
`--role R` (redaction role, default `root`).

Examples:
```bash
seam call binre report target=06e1d4041f69ca58...        # cached RE report by sha256
seam call repo-inventory inventory root=C:/my/repo       # file/LOC census
seam call sigil pack input=C:/my/file.txt --writes       # pack a file (writes a .sgl)
seam perceive "C:/Users/bruke/Pre Atlas" --writes --json # the whole perceive stage, as JSON
```

The `--json` manifest:
```json
{
  "pipeline": "perceive",
  "target": "C:/my/repo",
  "produced_at": "2026-06-26T12:00:00+00:00",
  "receipts": [ { "tool": "...", "sha256": "...", "status": "ok", "data": {…} }, … ],
  "summary": { "ok": 3, "error": 0, "total": 3 }
}
```
Exit code is `0` only when every receipt is `ok`, so a script can gate on it. A write capability
called without `--writes` shows up as `status: error` with `writes are gated off` — visible in the
manifest, never silently skipped.

## Path 2 — HTTP (any client, any language, any model)

Start the gateway once, then POST to `/seam/call`:

```powershell
cd services/atlas-map-api
$env:DESCRIBE_GATEWAY_CLI=1; $env:DESCRIBE_GATEWAY_WRITES=1
.venv\Scripts\python.exe -m uvicorn atlas_map_api.server:app --host 127.0.0.1 --port 3072
```
```bash
curl.exe -s localhost:3072/seam/call -H "content-type: application/json" \
  -d '{"surface":"binre","capability":"report","args":{"target":"06e1d404..."}}'
# -> one Receipt as JSON
```
Body fields: `surface`, `capability`, `args` (object), optional `sha256` (overrides the lifted key).
A "workflow" over HTTP is just several of these POSTs in sequence, your code reading each receipt.

## Path 3 — MCP `atlas_call` (inside Claude)

The same gateway, exposed as the `atlas_call` MCP tool. Convenient in a Claude session; identical
semantics.

## Surface reference

> `R` = read, `W` = write (needs `--writes` / `DESCRIBE_GATEWAY_WRITES=1`).

### `sigil` (cli) — the join-key minter
Content-addressable code↔dictionary↔pixels codec. The canonical content-address source.
- `info {input}` — R — read a container header. Returns `{magic, sha256, orig_len, comp_len, …}`.
- `pack {input}` — W — squeeze a file into a `.sgl` (or `.png`). Returns `{sha256, ratio, dict_id, …}`.
- `unpack {input}` — W — restore a container to the original (hash-verified). Returns `{sha256, …}`.
- Join key: sha256 of the **original** bytes. `pack → info → unpack` all return the same key.

### `binre` (cli) — reverse-engineering report
- `report {target}` — R — read a **cached** merged `report.json` for a binary, no Ghidra (fits 20s).
  `{target}` is a bare sha256 or a binary path. Returns `{sha256, sample, duration_ms, stages, …}`.
  `found:false` when no cached report exists (run the full pipeline first).
- Join key: sha256 of the binary.

### `groundwork-cli` (cli) — repo structural index
- `index {root}` — W — walk a repo into `<root>/.groundwork/system-index.json` and print
  `{sha256, subsystem_count, artifacts}`. Join key = sha256 of the canonical index (the wall-clock
  `generated_at` and absolute `repo_root` are stripped, so the key is stable across runs/paths).

### `st3gg` (cli) — steganographic carrier analysis
- `analyze {input} --json` — R — read-only statistical analysis of a PNG carrier (LSB ratios,
  chi-square, channel stats). Returns `{sha256, file, analysis}`. Join key = sha256 of the carrier
  bytes. The `decode`/payload path is an injection channel and is **deliberately not exposed**.

### `delta-scp-demo` (http) — compression service
- `healthz` — R — `GET /healthz` → `{ok, service, mode}`. The always-available liveness read.
- `get-job {id}` — R — `GET /jobs/{id}` → a compression job by id. Needs a job minted by a prior
  `POST /jobs` (a write). The server must be running (gateway proxies, does not auto-start it).
- Consumes a sha (job ids are UUIDs); mints no content-address.

### `code-recon` (cli) — the orient gate
- `orient {root}` — R — run the recon orient gate **read-only** (never regenerates) and content-
  address the cached delta-scp map. Returns `{verdict (FRESH/STALE/MISSING), action, map, tokens,
  sha256}`. `MISSING` is a valid `ok` answer (no map yet), with `sha256: null`. Join key = sha256
  of the map.

### `repo-inventory` (cli) — multi-system census
- `inventory {root}` — R — per-system file/LOC counts, primary language, cross-system deps.
  Returns `{sha256, system_count, total_files, total_code_lines, systems}`. Join key = sha256 of the
  canonical inventory (absolute root excluded, so it's path-stable).
