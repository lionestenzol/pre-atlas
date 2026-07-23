# Self-Describing Surfaces

Every live Pre Atlas service can **narrate itself** to a caller — its state and the
actions available — through a headless, access-scoped descriptor (a "form"). The
same descriptor serves a blind human (`format=text`), a CLI, and an LLM agent
(`format=json` / MCP): all of them consume the system through narration instead of
pixels. This is layer-1 of the capability-registry ("OpenRouter for my services")
vision: one place that knows what every surface exposes, and hands each caller only
what they're cleared to see.

## The "test form" model

Like a standardized exam where each test-taker gets a different form, two callers
asking the same surface "what can I do?" get **different forms** based on their
access. The more critical a capability, the fewer descriptors leak — need-to-know.

## Three axes (per capability)

| Axis | Values | Meaning |
|---|---|---|
| `direction` | read / write | observe vs mutate |
| `exposure` | public / agent / internal | who may see it at all |
| `criticality` | 0–3 | routine read → ordinary write → admin/config → destructive |

## Roles (the test-takers)

| role | clearance | exposure | directions | notes |
|---|---|---|---|---|
| `anon` | 0 | public | read | no token |
| `agent-ro` | 1 | public, agent | read | read-only agent |
| `agent` | 1 | public, agent | read, write | default agent — gets **less** than the human |
| `operator` | 2 | +internal | read, write | hands-on human |
| `root` | 3 | all | all | full |

## Redaction ladder

Per capability, given the caller's role:

- wrong exposure / wrong direction → **redacted** (counted, unnamed)
- `clearance >= criticality` → **full** (label + invoke + needs)
- `clearance == criticality − 1` → **locked** (named, no invoke — one step away)
- `clearance <= criticality − 2` → **redacted** (counted, unnamed)

`criticality >= 2` redactions also emit an **existence proof** — an HMAC hash
(`redacted_proofs`) that proves *something* is there without disclosing what, so an
over-cleared auditor can verify completeness without a need-to-know leak.

## Enforcement (this is a lock, not a demo)

The caller's role is **derived from the `X-Atlas-Token`** they present (no token =>
`anon`). The `?role=` query param can only **narrow** — a root operator may preview
the agent form, but an unauthenticated caller asking `?role=root` still gets `anon`.
Extra tokens map to roles via `ATLAS_ROLE_TOKENS` env or a gitignored
`.atlas-role-tokens.json` (`{"<token>": "<role>"}`); the write token is always `root`.

## Surfaces (declarative, evidence-backed)

Each service declares itself in `services/<name>/atlas.surface.json`. Every declared
`invoke` endpoint is a **real route** in that service — enforced by
`scripts/verify_overlays.py` (no hallucinated furniture). 10 surfaces, 74
capabilities as of 2026-06-24: aegis-fabric, atlas-map-api, canvas-engine, cortex,
delta-kernel, droplist, memory-hub, optogon, search-stack, uasc-executor.

## Use it

```bash
# HTTP — unauthenticated caller (anon); ?role=root is ignored (cannot escalate)
curl 'http://127.0.0.1:3072/describe/delta-kernel?role=root'

# HTTP — text narration (screen reader / CLI / TTS)
curl 'http://127.0.0.1:3072/describe/droplist?format=text'

# HTTP — authenticated, narrowing to an agent preview
curl -H "X-Atlas-Token: $(cat .atlas-write-token)" \
     'http://127.0.0.1:3072/describe/delta-kernel?role=agent'

# discovery
curl 'http://127.0.0.1:3072/describe'
```

Pass `?live=1` to fill the `state` slot — the gateway probes the surface's own
public health read and embeds the report, so the form shows what's true *right now*
(the "contextually self-aware" surface).

Agents reach the same things over MCP: `atlas_describe(surface, role="agent")`,
`atlas_describe_list()`, and `atlas_call(surface, capability, args)` — the gateway's
uniform front door for agents (MCP callers act as role `agent`).

## Layer 3 — the call gateway (`POST /call`)

One front door invokes a capability **by name** — no host/port/route knowledge.
Access is enforced by the registry: you can only call a capability your own
`/describe` form shows (not locked, not redacted). The gateway resolves
surface→port (launch.json runtime truth → snapshot fallback) and proxies the
declared route to the live service.

```bash
# anon may invoke a public read through the gateway
curl -X POST 'http://127.0.0.1:3072/call' \
     -H 'Content-Type: application/json' \
     -d '{"surface":"triangulation","capability":"healthz"}'

# an agent/operator invokes an agent-visible capability with args
curl -X POST 'http://127.0.0.1:3072/call' -H "X-Atlas-Token: $(cat .atlas-write-token)" \
     -H 'Content-Type: application/json' \
     -d '{"surface":"triangulation","capability":"verify","args":{"elements":[...]}}'
```

**Dispatch by kind:** http surfaces proxy the declared route; cli surfaces run the
declared command (argv-only, no shell). **Writes are opt-in** (`DESCRIBE_GATEWAY_WRITES=1`)
and "write" is decided by the HTTP **verb** (POST/PUT/PATCH/DELETE), not just the
`direction` label — the verb is ground truth. A role-token may be **write-scoped**
to specific surfaces (`{"role":"agent","write_surfaces":["droplist"]}` in
`.atlas-role-tokens.json`); a malformed scope fails closed (deny-all). **cli is opt-in** (`DESCRIBE_GATEWAY_CLI=1`).
ui/websocket aren't invocable yet (422). Refusals: 404 unknown, 403 not visible to
your role, 400 undeclared args, 422 non-invocable kind / no port, 501 write|cli
gated, 502 upstream unreachable.

**Hardening (adversarial-reviewed):** path-param values are percent-encoded (no
`../` traversal or `?`-query injection past the declared route); caller args must
match the capability's declared params (no smuggling); cli rejects leading-dash
values + shell metachars, resolves the exe via PATH (no cwd hijack), and caps
arg size; surface names are charset-restricted (no filesystem traversal); internal
URLs/argv/cwd are withheld from low-clearance callers.

## Verify

```bash
./.venv/Scripts/python.exe scripts/verify_overlays.py   # every endpoint is real
./.venv/Scripts/python.exe -m pytest -q                 # 98 tests
```

## Deferred (next bricks)

Per-surface write-scoped tokens (finer than role-level), full call *normalization*
(one uniform request envelope, not just response), **ui/websocket** invocation, and
live `state` population (the `state:null` slot).
