# Adding a new tool to the seam

The recipe for wiring an 8th (9th, …) tool. It takes one overlay file, and usually one thin
wrapper script. No changes to the gateway.

## The contract

A tool is **seam-ready** when one of these is true:

- **CLI**: invoking it prints, to **stdout**, a single JSON object that contains a `sha256` (hex)
  field — the content-address of whatever it produced or read. The seam lifts that as the join key.
- **HTTP**: it's a service that returns a JSON body (any shape; an `{ok: …}` envelope is typical).

Anything the tool also writes (files, side effects) is fine; the seam only reads the stdout JSON or
the HTTP body.

## Decision: emit-or-wrap

Most existing tools either print human text (Rich/tables) or write files. You have two ways to make
one seam-ready:

1. **Edit the tool** to add a `--json` flag that prints the receipt. Do this when the tool is yours
   and the change is small and welcome (example: `gw index --json`, `st3gg analyze --json`).
2. **Wrap it** with a thin adapter in `tools/<name>/` that runs/imports the tool and prints the
   receipt. Do this when the tool is external, global (`~/.claude`), heavy, or you don't want to
   touch it (examples: `tools/binre/report.py`, `tools/repo-inventory/inv.py`,
   `tools/code-recon/orient_seam.py`). **Prefer wrapping** — it keeps seam code in this repo.

In both cases, make the content-address **stable**: strip wall-clock timestamps and absolute paths
before hashing, so the same content yields the same key across runs and machines.

## Steps

1. **Pick the engine and the artifact.** What does the tool produce or read, and what is its natural
   content-address? (a binary's sha, a file's bytes, a canonical index, a map.) If the tool already
   has a content-address, reuse it; don't invent a second one.

2. **Make it print a stdout JSON receipt** (edit or wrap). Minimum: `{"tool": "<name>", "sha256":
   "<hex>", …}`. Add a `found: false` + an `error` field for the "ran fine but nothing there" case,
   and exit non-zero only on a real failure (bad input, crash) — not on legitimate absence.

3. **Write the overlay** `tools/<name>/atlas.surface.json` (schema below). For a cli wrapper, the
   `invoke` references the script by a path **relative to repo root** (the gateway's cwd), e.g.
   `python tools/<name>/<script>.py {arg}`. For an absolute-path interpreter (a venv), put the
   absolute path as `argv[0]` and the script as a relative or absolute arg — but remember
   forward-slashes only (backslashes are rejected by the arg charset).

4. **Mark direction.** `read` for a pure read; `write` if it writes files/state (it will then need
   `--writes` / `DESCRIBE_GATEWAY_WRITES=1`). Set `criticality` (0 routine … 3 dangerous) and
   `exposure` (public/agent/internal) honestly — that's the redaction ACL.

5. **Prove it live** — standalone, then through the gateway into a Receipt:
   ```python
   from atlas_map_api import gateway
   from atlas_map_api.loader import load_snapshot
   from atlas_map_api.seam import Receipt
   gateway.CLI_ENABLED = True        # + gateway.WRITES_ENABLED = True for a write cap
   snap = load_snapshot()
   env = __import__("asyncio").run(gateway.call_capability(
       snap, "<name>", "<cap>", {"<arg>": "<value>"}, token=None, role_name="root"))
   print(Receipt.from_envelope(env, produced_at="2026-01-01T00:00:00+00:00").model_dump())
   ```
   Or just: `seam call <name> <cap> arg=value`.

6. **Add a regression test** to `services/atlas-map-api/tests/test_seam.py`: the overlay loads with
   the right kind/direction, `declared_params` resolves, and a representative stdout receipt lifts
   the join key through `Receipt.from_envelope`.

7. (Optional) **Add it to a runner pipeline.** If it's a repo-perceive tool, append it to `PERCEIVE`
   in `tools/seam/run.py`.

## The overlay schema

```json
{
  "surface": "<name>",                 // for http, MUST match the launch.json name -> port
  "kind": "cli",                       // cli | http (also ui | websocket | library)
  "lifecycle": "live",
  "headline": "one line: what it is and what its join key addresses",
  "capabilities": [
    {
      "id": "<cap>",                   // the gateway refuses any id not declared here
      "label": "human label",
      "direction": "read",             // read | write   (write -> needs DESCRIBE_GATEWAY_WRITES=1)
      "exposure": "agent",             // public | agent | internal
      "criticality": 0,                // 0..3, role clearance must meet it to see the invoke
      "invoke": "python tools/<name>/<script>.py {arg}",   // cli: argv; http: "GET /path/{id}"
      "needs": ["arg"],                // params the caller must supply
      "evidence": "file:path grounding this",
      "notes": "caveats: 20s timeout, forward-slash paths, what found:false means, etc."
    }
  ]
}
```

Rules the gateway enforces, so design around them:
- `argv[0]` (the executable) must be a **literal**, never a `{placeholder}`.
- `{param}` values are substituted positionally and must match `^[A-Za-z0-9_.,:/@=+][…-]*$` — no
  leading dash, **no backslash**, no shell metachars; max 32 args, 512 chars each.
- The whole call must finish within **20 seconds**. If the real work is slow (Ghidra, a huge walk),
  expose only a fast read path and say so in `notes`.

## Worked examples (read these before writing yours)

| Pattern | File | Engine | Join key |
|---|---|---|---|
| read a cached artifact | `tools/binre/report.py` | binre's `out/<sha>/report.json` | sha of the binary (the dir name) |
| import an engine function | `tools/repo-inventory/inv.py` | `inventory.py` `analyze()` | sha of the canonical inventory (root stripped) |
| shell a script read-only | `tools/code-recon/orient_seam.py` | `orient.mjs --json` | sha of the cached map (generated_at stripped) |
| add a `--json` flag | `groundwork-cli/.../cli.py` | gw itself | sha of the index (generated_at + repo_root stripped) |

## Checklist

- [ ] The tool prints a stdout JSON object with a `sha256` (cli), or returns JSON (http).
- [ ] The content-address is **stable** (timestamps / absolute paths stripped before hashing).
- [ ] `tools/<name>/atlas.surface.json` declares the surface + capabilities.
- [ ] `direction` is correct; writes are gated; `criticality`/`exposure` are honest.
- [ ] cli `invoke` uses a literal `argv[0]`, a repo-root-relative script path, forward slashes.
- [ ] The fast path fits the 20s timeout; slow paths are not exposed.
- [ ] Proven live through the gateway into a Receipt (the join key appears).
- [ ] A regression test in `test_seam.py`.
- [ ] If it's a dangerous channel (decode/exec/eval), it is **NOT** exposed; only the safe read is.
