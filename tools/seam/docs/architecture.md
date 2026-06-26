# Seam architecture

How the pieces fit: the gateway dispatches a call to a tool, the tool returns output, and the
seam normalizes that output into one content-addressed Receipt. Four parts.

## 1. The gateway

`services/atlas-map-api/src/atlas_map_api/gateway.py`. Entry point:
`call_capability(snap, surface, capability, args, token, role_name)`. It looks up the surface's
overlay, finds the capability, enforces access, and dispatches by `overlay.kind`:

- **`kind: "cli"`** → `_invoke_cli`: builds an argv and runs it as a subprocess.
- **`kind: "http"`** → `_invoke_http`: resolves the surface's base URL and proxies the route.

Both return a normalized envelope `{ok, code, surface, capability, kind, status, data, error, meta}`.

### Gating (fail-closed)

- CLI invocation is **off** unless `DESCRIBE_GATEWAY_CLI=1` (else a 501 refusal).
- A capability whose `direction` is `write` is refused unless `DESCRIBE_GATEWAY_WRITES=1`
  (for http, a `POST`/`PUT`/`DELETE` verb counts as a write). Refusals are returned, never thrown.

### CLI invocation safety

`_invoke_cli` is the security-sensitive path and is bounded on every axis:

- **argv-only, `shell=False`** — no shell, so no metacharacter expansion.
- **`shutil.which(argv[0])`** — the executable resolves to an absolute path; a caller value can
  never choose the binary. `argv[0]` in the overlay must be a literal, never a `{placeholder}`.
- **`build_argv`** substitutes `{param}` placeholders **positionally**, then appends any leftover
  args after a `--` end-of-options sentinel as `--key value`. Every substituted value must match
  `_SAFE_ARG` (`^[A-Za-z0-9_.,:/@=+][A-Za-z0-9_.,:/@=+-]*$`): **no leading dash** (no flag
  injection), **no backslash** (Windows paths must use forward slashes), no shell metachars.
  Caps: at most 32 args, 512 chars each.
- **20-second timeout** — a tool that blows it returns a 504 refusal. (This is why the heavy
  `binre` pipeline is NOT exposed; only its fast cached-report read is.)
- **cwd** = `repo_root / sub.path` when the surface has a subsystem entry, else `repo_root`. Tools
  that aren't registered in `launch.json` run with cwd = repo root, so a wrapper script is
  referenced by a path **relative to repo root** (e.g. `python tools/binre/report.py {target}`).

### HTTP invocation

`_invoke_http` resolves the base URL via `resolve_base_url`: it matches the **surface name** to a
`launch.json` entry's `name` and uses its `port` (`http://127.0.0.1:<port>`). So an http overlay's
`surface` field MUST match the launch name (e.g. `delta-scp-demo` → port 3012, not `delta-scp`).
The route is proxied with `httpx` (10s timeout); an unreachable server yields a 502. Path params
`{id}` in the invoke are filled from `args`.

## 2. The Receipt

`services/atlas-map-api/src/atlas_map_api/seam.py`. `Receipt` is a frozen pydantic model
(`seam.v1`):

```
seam_version  always "seam.v1"
tool          the surface name (from the envelope; "unknown" if unstamped)
sha256        the join key, or null
produced_at   ISO-8601 timestamp (stamped by the caller)
status        "ok" only when the underlying call succeeded; else "error"
data          the tool's parsed payload (cli: parsed stdout JSON; http: the JSON body)
error         populated when status is "error"
```

`Receipt.from_envelope(env, *, produced_at, sha256=None)` folds the gateway's envelope (success,
failure, or refusal) into this one shape. For a cli result it parses the tool's stdout as JSON and
**lifts the `sha256`** out of it as the join key (unless the caller supplied one, which wins).
`POST /seam/call` (in `server.py`) is the HTTP front door: it always returns exactly one Receipt.

## 3. The join key (content-address)

The `sha256` is a **content-address**: the same input always produces the same fingerprint. That
single property buys three things:

- **Caching / idempotency** — same fingerprint means you've seen this exact artifact before.
- **Provenance** — a Receipt records "tool T produced an artifact with this address."
- **Cross-tool verification** — two tools holding the same bytes report the same key.

Each tool addresses **its own** artifact, so keys are only expected to match when the bytes match.
Where a derived artifact carries a wall-clock stamp or an absolute path (gw's `system-index.json`,
code-recon's map, repo-inventory's census), the wrapper **strips those** before hashing, so the key
is stable for the same content across runs and machines. `sigil` is the canonical minter (its key is
over the original packed bytes); `delta-scp` consumes a key and mints none.

## 4. The overlay system

Each surface is declared by a `tools/<name>/atlas.surface.json` (also under `services/` and `apps/`).
The loader scans those three roots. Shape:

```json
{
  "surface": "binre",
  "kind": "cli",
  "lifecycle": "live",
  "headline": "one-line description",
  "capabilities": [
    {
      "id": "report",
      "label": "human label",
      "direction": "read",          // read | write
      "exposure": "agent",          // public | agent | internal
      "criticality": 0,             // 0 routine .. 3 dangerous
      "invoke": "python tools/binre/report.py {target}",
      "needs": ["target"],
      "evidence": "where this is grounded in source",
      "notes": "anything a caller should know"
    }
  ]
}
```

`describe.py` enforces a **role-scoped redaction ladder**: a role's clearance is compared to each
capability's `criticality` and `exposure`, so low-clearance callers see a capability only as a
redacted count, then by name without its `invoke`, then fully. The capability registry IS the ACL —
the gateway refuses any capability id that isn't declared.

## The wrapper pattern (how most tools get wired)

A tool that doesn't already print stdout JSON with a `sha256` gets a **thin adapter** in its
`tools/<name>/` directory, rather than editing the upstream tool. The adapter runs (or imports) the
real engine, computes/lifts the join key, and prints the seam receipt. This keeps the seam code in
this repo and never touches external or global (`~/.claude`) tools. Worked examples:
`tools/binre/report.py` (reads a cached artifact), `tools/repo-inventory/inv.py` (imports an engine
function), `tools/code-recon/orient_seam.py` (shells a node script read-only). See
[extending.md](extending.md).
