# Cortex

Python/FastAPI service on :3009. Atlas's autonomous execution layer (planner -> executor -> reviewer loop).

## Role: Ghost Executor (Optogon stack)

Per `doctrine/02_ROSETTA_STONE.md` Contracts 3 and 4, Cortex plays the **Ghost Executor** role in the Optogon stack:

```
Atlas (delta-kernel)  ->  [Directive.v1]  ->  Cortex  ->  [TaskPrompt.v1]  ->  Claude Code
                                              |
                                              Claude Code returns  ->  [BuildOutput.v1]  ->  InPACT Signal
```

The Ghost Executor role is implemented in `src/cortex/ghost_executor/`:

- `consume.py` - `consume_directive(directive, working_directory)` validates a Directive.v1 payload and formats it as a TaskPrompt.v1 for Claude Code
- `emit.py` - `emit_build_output(task_prompt_id, status, summary, ...)` wraps an execution result as a BuildOutput.v1 for Atlas and InPACT consumption
- `_validator.py` - shared jsonschema validator using `contracts/schemas/`

Cortex is **not renamed** to ghost-executor. Per `doctrine/04_BUILD_PLAN.md` Decision D6, the service keeps its existing name and this README documents the role alias.

### Example

```python
from cortex.ghost_executor import consume_directive, emit_build_output

# Receive a Directive from Atlas (via GET /api/atlas/next-directive)
task_prompt = consume_directive(directive_payload, working_directory="/repo")

# After Claude Code finishes executing the task, wrap the result
build_output = emit_build_output(
    task_prompt_id=task_prompt["id"],
    status="success",
    summary="Lesson 5 shipped to main",
    artifacts=[{"type": "file", "path": "apps/inpact/content/lessons/5.md"}],
    tokens_used=4200,
)
```

## Existing execution layer

The original Cortex responsibilities continue in:
- `agents/planner.py`, `agents/executor.py`, `agents/reviewer.py`
- `loop.py` - main autonomous loop
- `clients/delta_client.py`, `clients/aegis_client.py`, `clients/uasc_client.py`

The Ghost Executor module is an *additive* surface, not a replacement.

## Tests

```bash
cd services/cortex
pytest src/cortex/ghost_executor/tests/
```

## Ports

- :3009 - FastAPI server (main.py)
- Upstream: delta-kernel :3001, uasc-executor :3008, aegis-fabric :3002
