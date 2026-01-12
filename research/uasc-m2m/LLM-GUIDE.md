# UASC-M2M Guide for LLMs

You are working with a **command-address execution layer** that maps short command tokens (a.k.a. "glyphs") to full deterministic execution workflows.

> Think of it as **DNS for actions**:
> - DNS: `google.com` → IP address
> - UASC: `@WORK` → versioned execution profile / workflow graph

**Core idea:** clients send tiny addresses; servers hold all executable logic.

---

## What This System Is (and is NOT)

### IS:
- A compact **opcode/token** layer for invoking **pre-defined** workflows
- A registry that maps `cmd` → `profile_id@version` (or `graph_id@version`)
- A deterministic executor/interpreter that runs the workflow and returns results
- A control-plane pattern for APIs: **one endpoint** + **command tokens**

### IS NOT:
- Lossless "compression of arbitrary apps into one symbol"
- "Universal knowledge in one glyph"
- A Chinese-language requirement (Chinese glyphs were a metaphor only)

---

## Key Concepts

| Term | What It Is | Example |
|------|------------|---------|
| **Command Token (Glyph)** | Short command address (script-agnostic) | `@WORK`, `@WRAP`, `@BUILD`, `@C3` |
| **Registry** | Mapping from token → workflow ID + version | `@WORK → WORK_v1` |
| **Execution Profile / Graph** | Deterministic workflow definition | nodes, conditions, actions |
| **Action Handler** | Function that performs real work | `traffic.emergency_corridor()` |
| **Interpreter / Executor** | Runtime that expands token → runs workflow → returns result | token → profile → steps → result |
| **Trust Layer** | Auth + authorization to run commands | HMAC / roles / allowlists |

---

## Repository Layout

```
reference-implementation/
├── core/                   # Graph-based engine (advanced path)
│   ├── glyph.py             # Token / frame types (and domains, if used)
│   ├── registry.py          # Command → graph bindings (and graph store)
│   ├── interpreter.py       # Executes workflow graphs
│   └── trust.py             # Authority verification
├── actions/                 # Action handler modules
│   └── traffic_control.py
├── mvp/                    # Profile-based engine (ship-fast path)
│   ├── profiles/            # JSON workflow definitions (git-versioned)
│   │   ├── WRAP_v1.json
│   │   ├── WORK_v1.json
│   │   └── ...
│   ├── server.py            # HTTP API server with /exec
│   ├── cli.py               # Command-line client
│   ├── auth.py              # HMAC signature verification
│   └── executor.py          # Runs profile steps (shell/http/condition)
├── demo.py                  # End-to-end smoke test
└── api_example.py           # Minimal API usage example
```

**MVP rule:** Use `mvp/` first. It's the deployable path.
**Core graphs:** Use `core/` when you need richer orchestration.

---

## How to Test

```bash
cd reference-implementation

python demo.py        # Full system test (core graphs)
python api_example.py # API pattern demo
```

---

## How to Create a New Command (MVP Path)

### 1) Create JSON Profile

Path: `reference-implementation/mvp/profiles/MYCOMMAND_v1.json`

```json
{
  "id": "MYCOMMAND",
  "version": 1,
  "description": "What it does",
  "inputs": [
    { "name": "target", "type": "string", "required": true }
  ],
  "steps": [
    {
      "name": "do_thing",
      "type": "shell",
      "cmd": "echo ${target}"
    }
  ]
}
```

### 2) Bind Token → Profile in Registry

Registry maps token to a specific profile+version, e.g.:

- `@MYCMD → MYCOMMAND_v1`

(Implementation detail depends on `registry.db` schema; do NOT hardcode in the client.)

### 3) Execute It

CLI:
```bash
python mvp/cli.py @MYCMD target=hello
```

HTTP (dev mode, auth disabled):
```bash
curl -X POST http://localhost:8420/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd":"@MYCMD","target":"hello"}'
```

HTTP (with auth headers):
```bash
curl -X POST http://localhost:8420/exec \
  -H "Content-Type: application/json" \
  -H "X-UASC-Client: my-client-id" \
  -H "X-UASC-Timestamp: 1704500000" \
  -H "X-UASC-Signature: <hex_hmac_sha256>" \
  -d '{"cmd":"@MYCMD","target":"hello"}'
```

---

## How to Create a New Command (Core Graph Path)

Use this when you need richer orchestration (conditions, parallel execution, etc.)

```python
from core.registry import Registry, ExecutionGraph
from core.glyph import Domain

registry = Registry(
    registry_id="my-registry",
    domain=Domain.CUSTOM,
    authority=0x100
)

graph = ExecutionGraph(
    graph_id="my-graph",
    name="my_command",
    version="1.0.0",
    domain="custom",
    inputs=[{"name": "target", "type": "string", "required": True}],
    outputs=[{"name": "status", "type": "string"}],
    nodes={
        "start": {"type": "entry", "next": "work"},
        "work": {
            "type": "action",
            "operation": "my.action",
            "params": {"target": "inputs.target"},
            "next": "done"
        },
        "done": {
            "type": "exit",
            "outputs": {"status": "complete"}
        }
    }
)

registry.register_graph(graph)
registry.bind_glyph(0x8100, "my-graph")
```

---

## Node Types Reference (Graph/Profile)

| Type | Purpose | Fields |
|------|---------|--------|
| `entry` | Start | `next` |
| `exit` | End | `outputs` |
| `action` | Do work | `operation`, `params`, `next` |
| `condition` | Branch | `expression`, `on_true`, `on_false` |

Condition example:
```json
{
  "id": "check",
  "type": "condition",
  "expression": "priority >= 3",
  "on_true": "urgent_path",
  "on_false": "normal_path"
}
```

Action example:
```json
{
  "id": "clear",
  "type": "action",
  "operation": "traffic.emergency_corridor",
  "params": { "zone": "inputs.zone" },
  "next": "success"
}
```

---

## Token Conventions

Tokens are ASCII by default for portability:

- `@WORK`, `@WRAP`, `@BUILD`, `@DEPLOY`
- Short IDs like `@C3` are allowed (useful in constrained environments)

Chinese characters are optional display aliases only (never required).

---

## Domains (Optional)

Domains are useful for separating registries, not required for MVP.

```python
class Domain(IntEnum):
    CUSTOM = 0xF
    # Add more only when you need domain separation
```

---

## Security Envelope (HMAC)

Client sends:
- `X-UASC-Client: <client_id>`
- `X-UASC-Timestamp: <unix_seconds>`
- `X-UASC-Signature: <hex_hmac_sha256>`

Signing string (exact bytes, no whitespace changes):
```
payload = f"{timestamp}\n" + <raw_request_body_bytes>
signature = HMAC_SHA256(client_secret, payload)
```

Server checks:
1. Timestamp within allowed window (e.g., 60s) to prevent replay
2. Signature matches
3. Client authorized for the requested command token

Content-Type must be fixed (`application/json`). Body must be exact bytes used in signature.

---

## Canonical /exec Request/Response

### Request
```json
{
  "cmd": "@WORK",
  "project": "./myapp",
  "mode": "verbose"
}
```

- `cmd` (required): Command token
- All other fields: Arguments passed to profile/graph inputs
- Arguments are validated against profile's `inputs` definition

### Response (Success)
```json
{
  "status": "success",
  "run_id": "abc123",
  "duration_ms": 1250,
  "steps": [
    {"name": "step1", "status": "success", "duration_ms": 500},
    {"name": "step2", "status": "success", "duration_ms": 750}
  ],
  "outputs": {
    "result": "completed",
    "files_processed": 42
  }
}
```

### Response (Error)
```json
{
  "status": "failed",
  "run_id": "abc124",
  "error": "Step 'build' failed: exit code 1",
  "steps": [
    {"name": "install", "status": "success", "duration_ms": 200},
    {"name": "build", "status": "failed", "duration_ms": 100}
  ]
}
```

### Response (Auth Error)
```json
{
  "error": "Invalid signature",
  "status": 401
}
```

---

## Traditional API vs UASC Pattern

| Traditional API | UASC |
|-----------------|------|
| Client sends verbose instructions | Client sends `cmd` address only |
| Many endpoints | One `/exec` endpoint |
| Behavior duplicated across clients | Behavior centralized in server profiles |
| Harder to audit drift | Versioned profiles + full audit log |
| Schema drift | Stable command interface |

---

## When Helping Users (LLM Checklist)

1. **Add a command**: Create profile JSON + bind token in registry
2. **Add an action**: Implement handler function + register operation name
3. **Test**: Run `demo.py` and a sample `/exec` call
4. **Debug**: Check `steps` array and `error` field in response
5. **Extend domains**: Only if multiple registries are required

---

## Quick Mental Model

User triggers: `@C3 zone=5`

System does:
1. Parse token `@C3`
2. Registry lookup → `emergency_priority` workflow (versioned)
3. Merge args/context → `{zone: 5, priority: 5}`
4. Execute workflow → start → check → clear_corridor → success
5. Return outputs → `{corridor_cleared: true, signals_affected: 9}`

The token stays tiny; the logic stays server-side.

---

## Files to Read First

1. `reference-implementation/demo.py` - See the full flow
2. `reference-implementation/core/registry.py` - The token→workflow mapping
3. `reference-implementation/mvp/profiles/*.json` - Example profiles
4. `reference-implementation/mvp/server.py` - HTTP API implementation
