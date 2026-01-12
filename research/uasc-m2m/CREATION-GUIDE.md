# UASC-M2M Creation Guide

A practical guide for future development of the UASC-M2M system.

---

## Quick Reference

```
UASC-M2M = Key Warehouse + Execution Engine

Client sends:   @C3 + zone=5      (25 bytes)
Server holds:   Full workflow     (execution graph)
Result:         Deterministic     (auditable, versioned)
```

---

## 1. Creating a New Glyph Command

### Step 1: Define the Execution Graph

Create a JSON profile in `reference-implementation/mvp/profiles/`:

```json
{
  "id": "MYCOMMAND",
  "version": 1,
  "description": "What this command does",
  "author": "your-name",
  "created": "2026-01-06",

  "inputs": [
    {
      "name": "target",
      "type": "string",
      "required": true,
      "description": "Target to operate on"
    },
    {
      "name": "mode",
      "type": "string",
      "default": "normal",
      "description": "Execution mode"
    }
  ],

  "steps": [
    {
      "name": "step_one",
      "type": "shell",
      "cmd": "echo Starting...",
      "description": "First step"
    },
    {
      "name": "step_two",
      "type": "shell",
      "cmd": "echo Target is: ${target}",
      "condition": "mode == 'verbose'",
      "description": "Conditional step"
    }
  ],

  "on_success": {
    "type": "log",
    "message": "Command completed"
  },
  "on_failure": {
    "type": "log",
    "message": "Command failed",
    "level": "error"
  }
}
```

### Step 2: Register in the Registry

In Python code:

```python
from core.registry import Registry, ExecutionGraph
from core.glyph import Domain

# Create registry
registry = Registry(
    registry_id="my-registry-001",
    domain=Domain.SMART_CITY,
    authority=0x100
)

# Create execution graph
graph = ExecutionGraph(
    graph_id="my-command-001",
    name="my_command",
    version="1.0.0",
    domain="smart_city",
    inputs=[
        {"name": "target", "type": "string", "required": True}
    ],
    outputs=[
        {"name": "status", "type": "string"}
    ],
    nodes={
        "start": {"type": "entry", "next": "do_work"},
        "do_work": {
            "type": "action",
            "operation": "my_namespace.my_action",
            "params": {"target": "inputs.target"},
            "next": "success"
        },
        "success": {
            "type": "exit",
            "outputs": {"status": "completed"}
        }
    }
)

# Register and bind
registry.register_graph(graph)
registry.bind_glyph(0x8010, "my-command-001")  # @M1
```

### Step 3: Create Action Handler

In `reference-implementation/actions/`:

```python
def register_my_actions(registry):
    """Register custom action handlers."""

    def my_action_handler(params: dict) -> dict:
        target = params.get('target')
        # Do actual work here
        return {"result": "success", "processed": target}

    registry.register("my_namespace.my_action", my_action_handler)
```

### Step 4: Execute

```python
from core.glyph import GlyphFrame, Domain

frame = GlyphFrame(
    domain=Domain.SMART_CITY,
    authority=0x100,
    glyph_code=0x8010,
    context={"target": "my-target"}
)

result = interpreter.execute(frame)
print(result.status)  # "success"
```

---

## 2. Execution Graph Node Types

| Type | Purpose | Required Fields |
|------|---------|-----------------|
| `entry` | Start point | `next` |
| `exit` | End point | `outputs` |
| `action` | Execute operation | `operation`, `params`, `next` |
| `condition` | Branch logic | `expression`, `on_true`, `on_false` |
| `parallel` | Concurrent execution | `branches`, `join_strategy` |
| `loop` | Iteration | `condition`, `body`, `next` |

### Condition Examples

```json
{
  "id": "check_priority",
  "type": "condition",
  "expression": "priority >= 3",
  "on_true": "high_priority_path",
  "on_false": "normal_path"
}
```

### Action Examples

```json
{
  "id": "fetch_data",
  "type": "action",
  "operation": "sensor.read",
  "params": {
    "zone": "inputs.zone",
    "metrics": ["temperature", "humidity"]
  },
  "next": "process_data"
}
```

---

## 3. Glyph Code Allocation

### Code Ranges

| Range | Purpose |
|-------|---------|
| `0x0000-0x7FFF` | Reserved (Unicode CJK) |
| `0x8000-0x8FFF` | Standard commands |
| `0x9000-0x9FFF` | Domain-specific |
| `0xA000-0xFFFE` | Custom/local |
| `0xFFFF` | Reserved |

### Token Format

```
Glyph Code → Token
0x8001    → @A1
0x8002    → @A2
0x8003    → @C3  (C = Control)
0x8004    → @N4  (N = Network)
0x9001    → @S1  (S = Sensor)
```

---

## 4. Adding New Domains

### Define Domain

In `core/glyph.py`:

```python
class Domain(IntEnum):
    RESERVED = 0x0
    SMART_CITY = 0x1
    AEROSPACE = 0x2
    MARITIME = 0x3
    # Add new domain:
    MY_DOMAIN = 0xC  # Use 0x0-0xF
```

### Create Domain Registry

```python
registry = Registry(
    registry_id="my-domain-registry",
    domain=Domain.MY_DOMAIN,
    authority=0x001  # Your authority ID
)
```

---

## 5. Trust Chain Setup

### Hierarchy

```
UASC Consortium (Root)
    └── Domain Authority (e.g., Smart City Consortium)
        └── Local Authority (e.g., City of Tokyo)
            └── Your Registry
```

### Mock Trust Chain (Development)

```python
from core.trust import create_mock_trust_chain

trust = create_mock_trust_chain(
    domain=Domain.MY_DOMAIN,
    authority=0x100,
    authority_name="My Organization"
)
```

### Production Trust Chain

```python
# Load certificates
root_cert = load_certificate("/etc/uasc/root.crt")
domain_cert = load_certificate("/etc/uasc/domain.crt")
local_cert = load_certificate("/etc/uasc/local.crt")

trust_store = TrustStore(root_cert)
trust_store.add_domain_cert(Domain.MY_DOMAIN, domain_cert)
trust_store.add_authority_cert(Domain.MY_DOMAIN, 0x100, local_cert)
```

---

## 6. Step Types for Profiles

### Shell Step

```json
{
  "name": "run_command",
  "type": "shell",
  "cmd": "echo Hello",
  "timeout_seconds": 60,
  "continue_on_error": false,
  "capture_output": true,
  "store_as": "result_var"
}
```

### Conditional Step

```json
{
  "name": "conditional_step",
  "type": "shell",
  "cmd": "npm test",
  "condition": "pkg_manager == 'npm'"
}
```

### Platform-Specific

```json
{
  "name": "windows_only",
  "type": "shell",
  "cmd": "dir",
  "platform": "windows"
},
{
  "name": "unix_only",
  "type": "shell",
  "cmd": "ls -la",
  "platform": "unix"
}
```

---

## 7. Testing Your Commands

### Unit Test

```python
def test_my_command():
    # Setup
    registry = create_test_registry()
    interpreter = create_test_interpreter(registry)

    # Create frame
    frame = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x100,
        glyph_code=0x8010,
        context={"target": "test"}
    )

    # Execute
    result = interpreter.execute(frame)

    # Assert
    assert result.status == "success"
    assert result.outputs["status"] == "completed"
```

### Integration Test

```bash
# Start server
python reference-implementation/mvp/server.py &

# Send command via CLI
python reference-implementation/mvp/cli.py @BUILD project=./myapp

# Or via curl
curl -X POST http://localhost:8420/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd": "@BUILD", "project": "./myapp"}'
```

---

## 8. Error Handling

### In Execution Graphs

```json
{
  "error_handling": {
    "default": "retry",
    "max_retries": 3,
    "fallback": "safe_mode_node"
  }
}
```

### Error Node

```json
{
  "id": "handle_error",
  "type": "exit",
  "status": "failed",
  "outputs": {
    "error": "Operation failed",
    "code": "ERR_001"
  }
}
```

---

## 9. File Structure

```
UASC-M2M/
├── reference-implementation/
│   ├── core/
│   │   ├── glyph.py        # Glyph encoding/decoding
│   │   ├── registry.py     # Key warehouse
│   │   ├── interpreter.py  # Execution engine
│   │   └── trust.py        # Trust chain
│   ├── actions/
│   │   └── *.py            # Action handlers
│   ├── mvp/
│   │   ├── profiles/       # JSON execution profiles
│   │   ├── server.py       # HTTP server
│   │   ├── cli.py          # CLI client
│   │   └── executor.py     # Profile executor
│   ├── demo.py             # Demo script
│   └── api_example.py      # API pattern demo
└── spec/
    ├── 01-REGISTRY-SPECIFICATION.md
    ├── 02-GLYPH-ENCODING-STANDARD.md
    ├── 03-AUTHORITY-MODEL.md
    └── 04-INTERPRETER-SPECIFICATION.md
```

---

## 10. Checklist for New Features

- [ ] Define execution graph (nodes, actions, conditions)
- [ ] Allocate glyph code in valid range
- [ ] Create action handlers if needed
- [ ] Register graph in registry
- [ ] Bind glyph code to graph
- [ ] Add JSON profile (if using MVP server)
- [ ] Write tests
- [ ] Document inputs/outputs
- [ ] Test via CLI and API

---

## 11. Common Patterns

### Sequential Execution

```
start → step1 → step2 → step3 → success
```

### Conditional Branching

```
start → check_condition
            ├── (true)  → action_a → success
            └── (false) → action_b → success
```

### Error Fallback

```
start → try_action
            ├── (success) → success
            └── (error)   → fallback_action → partial_success
```

### Parallel with Join

```
start → parallel_split
            ├── branch_a ─┐
            ├── branch_b ─┼→ join → success
            └── branch_c ─┘
```

---

## 12. Quick Commands

```bash
# Run demo
cd reference-implementation
python demo.py

# Run API example
python api_example.py

# Start server
python mvp/server.py

# Execute command
python mvp/cli.py @WORK
python mvp/cli.py @BUILD project=./myapp

# Test modules
python -c "from core.glyph import *; print('OK')"
```

---

## Summary

1. **Glyphs** = Short symbolic addresses (@C3, @N4)
2. **Registry** = Key warehouse mapping glyphs → graphs
3. **Graphs** = Deterministic execution workflows
4. **Actions** = Pluggable operation handlers
5. **Interpreter** = Runtime that executes graphs

The power is in the separation: clients send addresses, servers hold logic.
