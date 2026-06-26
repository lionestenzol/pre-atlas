# seam — model-agnostic runner for the perceive → compile → carry stack

A standalone CLI over the atlas-map capability gateway. **No Claude, no MCP, no server
required** — it drives the same gateway the HTTP endpoint uses, in-process, and normalizes
every tool's output into one content-addressed `Receipt`. Any caller that can run a command
(a human, a shell script, a cron job, any LLM/agent) can use it.

## Use

```bash
seam list                                   # every registered surface + capability
seam call <surface> <capability> k=v ...    # call one tool, print its Receipt
seam perceive <repo> [--writes]             # fan out the repo-perceive tools -> manifest
```

Examples:

```bash
seam call binre report target=06e1d404...           # cached RE report by sha256
seam call repo-inventory inventory root=C:/my/repo   # file/LOC census
seam call sigil info input=C:/my/file.sgl            # read a sigil container header
seam perceive "C:/Users/bruke/Pre Atlas" --writes    # inventory + orient + gw index
```

Add `--json` for a machine-readable manifest (`{pipeline, target, produced_at, receipts[], summary}`).
Exit code is `0` when every receipt is `ok`, `1` otherwise — so scripts can gate on it.

## Three ways to reach the seam (all model-agnostic)

| Surface | Caller | How |
|---|---|---|
| **`seam` CLI** (this) | any shell / script / agent | `seam call ...` — in-process, no server |
| **HTTP** `POST /seam/call` | any networked client / language / model | `{surface, capability, args}` against `:3072` |
| **MCP** `atlas_call` | Claude | the same gateway, in-session |

## Safety

- CLI invocation is on (this is a deliberate local operator tool).
- File-writing capabilities (`gw index`, `sigil pack`) require `--writes`; without it they
  return an `error: writes gated` receipt (visible in the manifest, never a silent skip).
- Every call goes through the gateway's arg-safety (argv-only, charset-checked, `shell=False`,
  20s timeout) — the runner adds no new execution surface.

The CLI is versioned here; `seam` on PATH is a thin shim at `C:\Users\bruke\bin\seam.cmd`.
