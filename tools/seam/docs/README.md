# Seam documentation

The maintained docs for the perceive → compile → carry integration seam. For a single
self-contained overview you can paste into an LLM or hand off, see
[`SEAM.md`](../../../SEAM.md) at the repo root.

## Start here

| Doc | Read it when you want to… |
|---|---|
| [overview](#what-the-seam-is) (below) | get the one-paragraph picture |
| [architecture.md](architecture.md) | understand the gateway, the Receipt, the join key, and the overlay system |
| [usage.md](usage.md) | call the seam — the 3 access paths + a per-surface reference |
| [extending.md](extending.md) | add a NEW tool to the seam (overlay format, Receipt contract, checklist) |

## What the seam is

Seven separate tools (`sigil`, `binre`, `groundwork-cli`, `st3gg`, `delta-scp`, `code-recon`,
`repo-inventory`), each behind one **gateway** that you call with `{surface, capability, args}`.
Every call returns the same **Receipt** `{tool, sha256, status, data, error}`, and every result
carries a **content-address** (the `sha256` "join key"). That uniformity is what lets you call
any tool the same way, verify results by identity, and chain tools while confirming they hold
the same artifact.

## Quick start

```bash
seam list                                   # what's callable
seam call sigil info input=C:/path/file.sgl # call one tool
seam perceive "C:/path/to/repo" --writes    # a multi-tool pass over a repo
```

`seam` is on PATH (`~/bin/seam` for bash/WSL, `~/bin/seam.cmd` for PowerShell/cmd). The CLI
itself lives in [`../run.py`](../run.py); its own usage notes are in [`../README.md`](../README.md).

## Where the code is

- **Gateway + Receipt**: `services/atlas-map-api/src/atlas_map_api/` — `gateway.py` (dispatch,
  arg-safety, gating), `seam.py` (the `Receipt`), `server.py` (`POST /seam/call`).
- **Surfaces**: `tools/<name>/atlas.surface.json` (overlays) + any wrapper scripts beside them.
- **Runner**: `tools/seam/run.py`.
- **Tests**: `services/atlas-map-api/tests/test_seam.py`.
