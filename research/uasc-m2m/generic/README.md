# UASC-M2M Generic Framework

A simplified, extensible framework for building UASC-M2M applications.

## Quick Start

```python
from uasc_generic import UASC

# Create instance
uasc = UASC()

# Register a custom action
@uasc.action("greet")
def greet(params, context):
    return f"Hello, {params.get('name', 'World')}!"

# Register a command
uasc.register("@HELLO",
    steps=[
        {"action": "greet", "params": {"name": "{user}"}, "store_as": "message"},
        {"action": "log", "params": {"message": "{message}"}}
    ],
    inputs=[{"name": "user", "default": "World"}]
)

# Execute
result = uasc.execute("@HELLO", {"user": "Alice"})
print(result)  # [OK] @HELLO (0ms)
print(result.outputs)  # {'message': 'Hello, Alice!'}
```

## Built-in Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `shell` | Run shell command | `cmd`, `timeout`, `cwd`, `ignore_error` |
| `http` | HTTP request | `url`, `method`, `body`, `headers`, `timeout` |
| `log` | Log message | `message`, `level` |
| `set` | Set variable | `name`, `value` |
| `wait` | Sleep | `seconds` |
| `python` | Execute Python | `code` |

## Step Options

```json
{
  "name": "step_name",
  "action": "shell",
  "params": {"cmd": "echo {variable}"},
  "store_as": "output_var",
  "platform": "windows",
  "condition": "var == 'value'",
  "continue_on_error": true
}
```

## Run Demo

```bash
python uasc_generic.py --demo
```

## Start HTTP Server

```bash
python uasc_generic.py --server 8420
```

Then:
```bash
curl http://localhost:8420/commands
curl -X POST http://localhost:8420/exec -d '{"cmd": "@HELLO"}'
```

## Examples

See `examples.py` for comprehensive usage examples.
