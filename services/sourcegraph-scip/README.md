# sourcegraph-scip

Third tier of the Atlas context engine — symbol-precise code intel above zoekt.

## What sits where

| Layer | Answers | Backed by |
|---|---|---|
| `atlas-manifest.yaml` | Module-level import edges (coarse) | `audit/build_atlas_manifest.py` (auto) |
| `zoekt` :port-free MCP | Fast trigram + best-effort `sym:` ranking | `C:\Users\bruke\zoekt-win` |
| **sourcegraph-scip** (this) | **Precise def / ref / callers / hover per symbol** | This dir |

## How it works

1. `reindex.py` walks a fixed list of TS + Python services, runs `scip-typescript` / `scip-python` on each, drops one `<name>.scip` shard per service into `./index/`, then runs `scip expt-convert` on each shard to produce `<name>.db` (SQLite).
2. `sourcegraph_mcp.py` is a FastMCP stdio server. It fans queries across every `.db` shard and returns tagged results (`<service>: <path>:<line>`).
3. `atlas.surface.json` declares the 5 capabilities so atlas-map-api's overlay scanner picks the surface up — no separate registration needed for the atlas map itself.

## Coverage (2026-07-25)

```
14 shard(s), 18 MB
  aegis-fabric     40 docs, 1652 symbols
  atlas-map-api    34 docs, 1379 symbols
  canvas-engine    52 docs, 1416 symbols
  cognitive-sensor 157 docs, 4423 symbols
  delta-kernel     58 docs, 7236 symbols
  delta-scp        14 docs, 422 symbols
  droplist         62 docs, 1659 symbols
  memory-hub       7 docs, 204 symbols
  openclaw         24 docs, 337 symbols
  optogon          31 docs, 890 symbols
  perception       16 docs, 247 symbols
  search-stack     48 docs, 848 symbols
  triangulation    14 docs, 335 symbols
  ws-gateway       1 docs, 71 symbols
```

Missing: `cortex` (scip-python emits a broken index — `CircuitOpenError#` has def without SymbolInformation → `scip expt-convert` refuses). Follow-up: upstream fix or vendor patch.

## MCP tools

Registered at USER scope:

```powershell
claude mcp add sourcegraph-scip -s user -- `
  "C:\Python313\python.exe" `
  "C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\sourcegraph_mcp.py"
```

Tools:

| Tool | Args | Returns |
|---|---|---|
| `sourcegraph_defs(symbol)` | `symbol="WorkController"` | `<service>: <file>:<line> · <full-scip-symbol>` for every def |
| `sourcegraph_refs(symbol)` | `symbol="WorkController"` | Every ref site (chunk-line granularity — open the file for exact col) |
| `sourcegraph_callers(file, line)` | `file="work-controller.ts", line=250` | Enclosing symbols at that line, tightest first |
| `sourcegraph_hover(symbol)` | `symbol="WorkController"` | Signature + docstring per def |
| `sourcegraph_status()` | — | Shard list, docs + symbol counts |

**Gotcha:** MCP tools registered mid-session only appear in the tool list in the **next** session. Restart Claude Code to see `mcp__sourcegraph-scip__*` in the deferred-tool set. This mirrors atlas-rag's same-day behavior.

## Rebuild the index

Full rebuild:

```bash
python "C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\reindex.py"
```

Freshness-gated (skips if newest shard <24h old — this is Layer 1 of the 3-layer failsafe):

```bash
python "C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\reindex.py" --if-stale
```

Scoped:

```bash
python reindex.py --project delta-kernel        # one service, both langs
python reindex.py --lang ts                     # all TS projects only
```

## Toolchain

- `scip` v0.9.0-dev at `C:\Users\bruke\go\bin\scip.exe` — built from `github.com/sourcegraph/scip` (go install rejects due to replace directives; clone + `go build ./cmd/scip`).
- `scip-typescript` 0.4.0 (npm global).
- `scip-python` 0.6.6 (npm global) — **patched on Windows**: the shipped `dist/scip-python.js` has `new RegExp(o.sep,"g")` which crashes on Windows because `path.sep = "\\"` is an invalid RegExp end. Patched inline to `new RegExp(o.sep === "\\" ? "\\\\" : "/", "g")`. Backup at `.js.bak`. If npm reinstalls the package, re-apply the one-liner.

## Reindex failsafe (3 layers)

Mirror of the zoekt pattern. Each layer catches a different miss — `--if-stale` (24h threshold) keeps them complementary rather than redundant.

| Layer | Trigger | Args | Where |
|---|---|---|---|
| L1 | `PreAtlas-SourcegraphScipReindex` — daily 05:40 (5min after zoekt) | *unconditional* | Windows scheduled task |
| L2 | governance_daemon cron `40 5 * * *` | `--if-stale` | `services/delta-kernel/src/governance/governance_daemon.ts` (gated by `GOVERNANCE_DAEMON=1`) |
| L3 | `PreAtlas-SourcegraphScipReindex-Boot` — user logon + 3min delay | `--if-stale` | Windows scheduled task |

Inspect:

```powershell
Get-ScheduledTask -TaskName "PreAtlas-SourcegraphScip*" | Format-Table TaskName, State
Get-ScheduledTaskInfo -TaskName "PreAtlas-SourcegraphScipReindex"
```

Manually re-register (if you moved reindex.py or Python):

```powershell
$python = "C:\Python313\python.exe"
$script = "C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\reindex.py"
$wd = "C:\Users\bruke\Pre Atlas\services\sourcegraph-scip"
$principal = New-ScheduledTaskPrincipal -UserId "bruke" -RunLevel Limited -LogonType Interactive

# L1 daily 05:40
Register-ScheduledTask -TaskName "PreAtlas-SourcegraphScipReindex" `
  -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $wd) `
  -Trigger (New-ScheduledTaskTrigger -Daily -At "05:40") `
  -Principal $principal -Force

# L3 logon (3min delay)
$trigL3 = New-ScheduledTaskTrigger -AtLogOn -User "bruke"
$trigL3.Delay = "PT3M"
Register-ScheduledTask -TaskName "PreAtlas-SourcegraphScipReindex-Boot" `
  -Action (New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --if-stale" -WorkingDirectory $wd) `
  -Trigger $trigL3 -Principal $principal -Force
```

## Doctrine

- Docker-free. Enterprise-license-free. Native Windows.
- Live-only in v1: no feed into `build_atlas_manifest.py` — the manifest already auto-generates module-level edges; symbol-cardinality enrichment is a v2 decision.
- Mirror of the zoekt path: same 3-layer failsafe shape, same MCP-over-stdio wrapper shape.
- See `[[project_atlas_rag_context_engine]]` (2026-07-22 direction) and `[[project_sourcegraph_fit_system_map]]` (what gap this actually fills).
