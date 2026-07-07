# The Seam — one front door over the perceive → compile → carry tool stack

> Single-file, self-contained overview. Paste it into an LLM or hand it to a person and
> they have the whole picture. Living docs (maintained with the code) are in
> [`tools/seam/docs/`](tools/seam/docs/README.md).

## The problem it solves

Pre Atlas grew a set of strong but **disconnected** tools: a reverse-engineering pipeline
(`binre`), a code/dictionary/pixel codec (`sigil`), a repo mapper (`gw`), a steganography
analyzer (`ST3GG`), a compression service (`delta-scp`), a recon orient gate (`code-recon`),
and a repo census (`repo-inventory`). Each ran its own way and spoke its own output format.
Nothing could hand work to anything else.

The seam connects them with three things:

1. **One way to call any tool** — `{surface, capability, args}` through a single gateway.
2. **One shape back** — every tool returns the same `Receipt`.
3. **A content-address on every result** — the `sha256` "join key", so you can prove two
   tools are holding the same artifact, cache by identity, and trace provenance.

It is a uniform **call + receipt** layer, not a self-driving ETL: you (a script, a cron job,
or any agent) compose the sequence; the seam guarantees every step is callable the same way,
verifiable, and content-addressed.

## The model: perceive → compile → carry

```
   PERCEIVE                 COMPILE                  CARRY
   look at an artifact      derive structure         move / store with identity
   ────────────────         ───────────────          ──────────────────────────
   binre    (RE report)     groundwork-cli (index)   sigil   (pack/unpack)
   code-recon (orient)      delta-scp     (skeleton)  ST3GG   (carrier)
   repo-inventory (census)                            delta-scp (job)
   ST3GG    (carrier stats)
        │                        │                        │
        └────────────────────────┴────────────────────────┘
                                 ▼
                    atlas-map gateway  (POST /seam/call)
                                 ▼
            Receipt { tool, sha256 (join key), status, data }
```

A tool can appear in more than one stage; the stages are a way to think about *what kind of
work* a call does, not a hard partition.

## The 7 surfaces

| Surface | Kind | Capability | You give it | Join key (sha256 of…) |
|---|---|---|---|---|
| `sigil` | cli | `info` / `pack` / `unpack` | a file / container | the original content (canonical) |
| `binre` | cli | `report` | a sha256 or binary path | the binary (cached RE report) |
| `groundwork-cli` | cli | `index` | a repo path | the canonical system-index |
| `st3gg` | cli | `analyze` | a PNG | the carrier file bytes |
| `delta-scp-demo` | http | `healthz` / `get-job` | (a job id) | — (consumes a sha, mints none) |
| `code-recon` | cli | `orient` | a repo path | the cached delta-scp map |
| `repo-inventory` | cli | `inventory` | a repo path | the canonical inventory |

Each tool content-addresses **its own** artifact. Two surfaces share a key only when they
hold the same bytes — e.g. `sigil pack → info → unpack` all return one key, which is how a
round-trip proves it didn't corrupt anything.

## The core mechanic: the Receipt

Every call returns one normalized envelope (`seam.v1`):

```json
{
  "seam_version": "seam.v1",
  "tool": "binre",
  "sha256": "06e1d4041f69ca58008316f9d072f0f73c1c957bca399382d60bd2e5f738fbf7",
  "produced_at": "2026-06-26T00:00:00+00:00",
  "status": "ok",
  "data": { "...": "the tool's own payload" },
  "error": null
}
```

- `status` is `ok` only when the underlying call succeeded; refusals and failures fold into
  `status: "error"` with a populated `error`.
- `sha256` (the join key) is lifted from the tool's own stdout JSON (cli) or supplied by the
  caller. `null` means the call ran but produced no content-address (e.g. a recon map that
  doesn't exist yet).

## How to call it (three model-agnostic paths)

First, two switches (the gateway is fail-closed by default):
`DESCRIBE_GATEWAY_CLI=1` enables the CLI tools; `DESCRIBE_GATEWAY_WRITES=1` also enables
file-writing capabilities (`gw index`, `sigil pack`).

**1. The `seam` CLI (no Claude, no MCP, no server):**
```bash
seam list                                   # every surface + capability
seam call binre report target=<sha256>      # one tool -> one Receipt
seam perceive "C:/path/to/repo" --writes    # inventory + orient + index -> a manifest
seam call repo-inventory inventory root=C:/path --json
```
`--json` emits a machine manifest `{pipeline, target, produced_at, receipts[], summary}`.
Exit code is `0` only if every receipt is `ok`, so scripts can gate on it.

**2. HTTP (any networked client / language / model):**
```bash
# start once (PowerShell):
cd services/atlas-map-api
$env:DESCRIBE_GATEWAY_CLI=1; $env:DESCRIBE_GATEWAY_WRITES=1
.venv\Scripts\python.exe -m uvicorn atlas_map_api.server:app --host 127.0.0.1 --port 3072
# then:
curl.exe -s localhost:3072/seam/call -H "content-type: application/json" \
  -d '{"surface":"repo-inventory","capability":"inventory","args":{"root":"C:/path"}}'
```

**3. MCP `atlas_call`** — the same gateway, in a Claude session.

## Adding a new tool (in brief)

A tool is seam-ready when it **prints a JSON object containing a `sha256` to stdout** (cli),
or **is an HTTP service returning a JSON envelope** (http). You register it with a
`tools/<name>/atlas.surface.json` overlay declaring its `invoke` string. If the tool can't
emit stdout JSON itself, write a thin wrapper in `tools/<name>/` that calls it and adds the
join key (the "binre pattern") — this avoids editing upstream/global tools. Full recipe and
a copy-paste checklist: [`tools/seam/docs/extending.md`](tools/seam/docs/extending.md).

## Status

- 7 surfaces wired, each proven live through the gateway into a Receipt.
- `atlas-map-api` test suite **161 passing**, seam suite **21**.
- Key commits: `a79c620` (foundation), `4cd83fc`/`1b646d5` (sigil carry), `d5f86f0`/`56ec8fd`
  (binre/gw/ST3GG/delta-scp fan-out + review fixes), `22705c0`/`28bbdcc` (gw `--json`),
  `9b3b4fc` (ST3GG `--json`), `b424c54` (code-recon + repo-inventory), `58e7384` (`seam` runner).
- Source: gateway + Receipt in `services/atlas-map-api/src/atlas_map_api/`
  (`gateway.py`, `seam.py`, `server.py`); overlays + wrappers in `tools/`; runner in `tools/seam/`.
