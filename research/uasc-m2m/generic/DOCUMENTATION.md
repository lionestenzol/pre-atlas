# UASC-M2M Generic Framework Documentation

## Overview

The UASC-M2M Generic Framework is a simplified, extensible task automation engine that allows you to define reusable actions, wire them into command sequences, and execute them by token. Think of it like a programmable shell alias system with conditional logic, variable passing, and machine-to-machine communication capabilities.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [What It Allows](#what-it-allows)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Core Concepts](#core-concepts)
6. [Built-in Actions](#built-in-actions)
7. [Registering Custom Actions](#registering-custom-actions)
8. [Registering Commands](#registering-commands)
9. [Step Options](#step-options)
10. [Variable Interpolation](#variable-interpolation)
11. [Conditional Execution](#conditional-execution)
12. [Error Handling](#error-handling)
13. [Binary Encoding (M2M)](#binary-encoding-m2m)
14. [HTTP Server API](#http-server-api)
15. [JSON Profile Format](#json-profile-format)
16. [Real-World Use Cases](#real-world-use-cases)
17. [API Reference](#api-reference)

---

## What It Does

The generic implementation (`uasc_generic.py`) is a simplified UASC-M2M framework that lets you:

### 1. Register Custom Actions
Define reusable functions that can be called from any command:
```python
@uasc.action("notify")
def notify(params, context):
    send_email(params['to'], params['message'])
    return "sent"
```

### 2. Register Commands
Map tokens like `@DEPLOY` to a sequence of steps:
```python
uasc.register("@DEPLOY",
    steps=[
        {"action": "shell", "params": {"cmd": "git pull"}},
        {"action": "shell", "params": {"cmd": "npm install"}},
        {"action": "notify", "params": {"to": "team", "message": "Deployed!"}}
    ]
)
```

### 3. Execute Commands
Run them with optional inputs:
```python
result = uasc.execute("@DEPLOY", {"branch": "main"})
```

---

## What It Allows

### 1. Automate Repetitive Tasks
Instead of typing multiple commands manually, define them once and run with a single token:
```python
# Before: manually run 5 commands every time
# After: one command does it all
uasc.execute("@DEPLOY")  # runs all 5 in sequence
```

### 2. Create Reusable Workflows
Define workflows as JSON or code, share them across projects, version control them:
```python
uasc.register_from_json("profiles/BACKUP.json")
uasc.register_from_json("profiles/DEPLOY.json")
uasc.register_from_json("profiles/CLEANUP.json")
```

### 3. Machine-to-Machine Communication
Send tiny 4-8 byte commands instead of large JSON payloads - ideal for IoT, embedded systems, and bandwidth-constrained environments:
```python
binary = uasc.encode("@SENSOR_READ")  # 4 bytes: 102a8001
# Send over network, IoT protocols, radio, satellite, etc.

# On receiving end:
token, context = uasc.decode(binary)
uasc.execute(token)
```

### 4. Build Custom Automation APIs
Expose your commands via HTTP server for remote execution:
```bash
# Start server
python uasc_generic.py --server 8420

# Execute remotely
curl -X POST http://localhost:8420/exec -d '{"cmd": "@BUILD"}'
```

### 5. Chain Operations with Data Passing
Output from one step automatically feeds into the next:
```python
steps=[
    {"action": "shell", "params": {"cmd": "git rev-parse HEAD"}, "store_as": "commit"},
    {"action": "shell", "params": {"cmd": "git log -1 --format=%s"}, "store_as": "message"},
    {"action": "log", "params": {"message": "Deploying {commit}: {message}"}}
]
```

### 6. Handle Platform Differences
Write once, run on Windows or Unix - the framework handles platform-specific steps:
```python
steps=[
    {"action": "shell", "params": {"cmd": "dir"}, "platform": "windows"},
    {"action": "shell", "params": {"cmd": "ls -la"}, "platform": "unix"}
]
```

---

## Installation

No external dependencies required. Copy `uasc_generic.py` to your project:

```bash
# Copy the file
cp generic/uasc_generic.py your_project/

# Or import directly
from uasc_generic import UASC
```

---

## Quick Start

```python
from uasc_generic import UASC

# 1. Create instance
uasc = UASC()

# 2. Register a custom action
@uasc.action("greet")
def greet(params, context):
    return f"Hello, {params.get('name', 'World')}!"

# 3. Register a command
uasc.register("@HELLO",
    steps=[
        {"action": "greet", "params": {"name": "{user}"}, "store_as": "message"},
        {"action": "log", "params": {"message": "{message}"}}
    ],
    inputs=[{"name": "user", "default": "World"}]
)

# 4. Execute
result = uasc.execute("@HELLO", {"user": "Alice"})
print(result)          # [OK] @HELLO (0ms)
print(result.outputs)  # {'message': 'Hello, Alice!'}
```

---

## Core Concepts

### Actions
Actions are the atomic units of work - functions that do something:
- `shell` - run a command
- `http` - make a request
- `log` - print a message
- Custom actions you define

### Commands
Commands are sequences of actions bound to a token:
- `@DEPLOY` might run: git pull -> npm install -> restart server -> notify team
- `@BACKUP` might run: stop service -> dump database -> compress -> upload -> start service

### Steps
Steps are individual action invocations within a command, with optional:
- Parameters
- Conditions
- Platform filters
- Error handling
- Output storage

### Context
Context is the shared state during execution:
- Input parameters
- Variables set by previous steps
- System info (platform, timestamp, etc.)

---

## Built-in Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `shell` | Run shell command | `cmd` (required), `timeout` (default: 60), `cwd`, `ignore_error` |
| `http` | Make HTTP request | `url` (required), `method` (default: GET), `body`, `headers`, `timeout` |
| `log` | Log/print message | `message` (required), `level` (default: info) |
| `set` | Set a variable | `name` (required), `value` (required) |
| `wait` | Pause execution | `seconds` (default: 1) |
| `python` | Execute Python code | `code` (required) |

### Examples

```python
# Shell command
{"action": "shell", "params": {"cmd": "npm install", "timeout": 120}}

# HTTP request
{"action": "http", "params": {"url": "https://api.example.com/deploy", "method": "POST", "body": {"version": "1.0"}}}

# Log message
{"action": "log", "params": {"message": "Deployment complete!", "level": "info"}}

# Set variable
{"action": "set", "params": {"name": "status", "value": "ready"}}

# Wait
{"action": "wait", "params": {"seconds": 5}}

# Python code
{"action": "python", "params": {"code": "result = 2 + 2"}}
```

---

## Registering Custom Actions

### Method 1: Decorator

```python
@uasc.action("send_slack")
def send_slack(params, context):
    channel = params.get('channel', '#general')
    message = params.get('message', '')
    # ... send to Slack API ...
    return {"sent": True, "channel": channel}
```

### Method 2: Direct Registration

```python
def send_email(params, context):
    to = params.get('to')
    subject = params.get('subject')
    body = params.get('body')
    # ... send email ...
    return {"sent": True}

uasc.register_action("send_email", send_email)
```

### Action Function Signature

```python
def my_action(params: dict, context: dict) -> any:
    """
    params: Parameters passed to this action
    context: Shared execution context with 'vars' dict

    Returns: Any value (stored if step has 'store_as')
    """
    # Access parameters
    value = params.get('key', 'default')

    # Access context variables (from previous steps)
    previous_result = context['vars'].get('some_var')

    # Return value (optional)
    return {"status": "done"}
```

---

## Registering Commands

### Method 1: Direct Registration

```python
uasc.register("@DEPLOY",
    steps=[
        {"action": "shell", "params": {"cmd": "git pull"}},
        {"action": "shell", "params": {"cmd": "npm install"}},
        {"action": "shell", "params": {"cmd": "npm run build"}},
        {"action": "log", "params": {"message": "Deployed!"}}
    ],
    name="Deploy",
    description="Deploy the application",
    inputs=[
        {"name": "branch", "default": "main"},
        {"name": "env", "default": "production"}
    ],
    on_success={"action": "log", "params": {"message": "Success!"}},
    on_failure={"action": "log", "params": {"message": "Failed!", "level": "error"}}
)
```

### Method 2: From JSON File

```python
uasc.register_from_json("profiles/DEPLOY.json")
```

### Method 3: From Dictionary

```python
command_def = {
    "id": "BACKUP",
    "description": "Backup database",
    "steps": [...]
}
uasc.register_from_dict(command_def)
```

---

## Step Options

Each step can have the following options:

```python
{
    # Required
    "action": "shell",              # Action to execute

    # Parameters for the action
    "params": {
        "cmd": "echo {variable}"    # Supports variable interpolation
    },

    # Optional
    "name": "my_step",              # Step name (for logging/debugging)
    "store_as": "output_var",       # Store output in this variable
    "platform": "windows",          # Only run on this platform (windows/unix)
    "condition": "env == 'prod'",   # Only run if condition is true
    "continue_on_error": true       # Continue even if this step fails
}
```

---

## Variable Interpolation

Use `{variable_name}` to insert variables into parameters:

```python
uasc.register("@GREET",
    steps=[
        {"action": "log", "params": {"message": "Hello, {name}!"}},
        {"action": "log", "params": {"message": "Today is {date}"}},
        {"action": "log", "params": {"message": "Running on {platform}"}}
    ],
    inputs=[{"name": "name", "default": "World"}]
)

uasc.execute("@GREET", {"name": "Alice"})
# Output:
# Hello, Alice!
# Today is 2025-01-08
# Running on windows
```

### Built-in Variables

| Variable | Description |
|----------|-------------|
| `{timestamp}` | Current ISO timestamp |
| `{date}` | Current date (YYYY-MM-DD) |
| `{platform}` | Current platform (windows/unix) |
| `{command}` | Current command token |

### Chaining Outputs

```python
steps=[
    {"action": "shell", "params": {"cmd": "hostname"}, "store_as": "host"},
    {"action": "shell", "params": {"cmd": "whoami"}, "store_as": "user"},
    {"action": "log", "params": {"message": "Running as {user} on {host}"}}
]
```

---

## Conditional Execution

### Platform-Specific Steps

```python
steps=[
    # Windows only
    {"action": "shell", "params": {"cmd": "dir"}, "platform": "windows"},

    # Unix only
    {"action": "shell", "params": {"cmd": "ls -la"}, "platform": "unix"}
]
```

### Condition Expressions

```python
steps=[
    # Only run if env is 'production'
    {
        "action": "shell",
        "params": {"cmd": "npm run build:prod"},
        "condition": "env == 'production'"
    },

    # Only run if debug is not empty
    {
        "action": "log",
        "params": {"message": "Debug mode enabled"},
        "condition": "debug != ''"
    }
]
```

### Supported Condition Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `==` | `env == 'prod'` | Equals |
| `!=` | `env != 'dev'` | Not equals |
| `== ''` | `var == ''` | Is empty |
| `!= ''` | `var != ''` | Is not empty |
| `true` | `true` | Always true |
| `false` | `false` | Always false |

---

## Error Handling

### Continue on Error

```python
steps=[
    {
        "action": "shell",
        "params": {"cmd": "risky_command"},
        "continue_on_error": true  # Won't stop execution if this fails
    },
    {"action": "log", "params": {"message": "This still runs!"}}
]
```

### Success/Failure Handlers

```python
uasc.register("@RISKY",
    steps=[...],
    on_success={
        "action": "log",
        "params": {"message": "All steps completed successfully!"}
    },
    on_failure={
        "action": "send_slack",
        "params": {"channel": "#alerts", "message": "Command failed!"}
    }
)
```

### Checking Results

```python
result = uasc.execute("@DEPLOY")

if result.status == "success":
    print("Deployment successful!")
else:
    print(f"Deployment failed: {result.error}")

# Check individual steps
for step in result.steps:
    print(f"{step.name}: {step.status}")
    if step.error:
        print(f"  Error: {step.error}")
```

---

## Binary Encoding (M2M)

For machine-to-machine communication, commands can be encoded to compact binary format:

### Encoding

```python
# Encode command to binary (4 bytes without context, 8 bytes with)
binary = uasc.encode("@SENSOR_READ", domain=1, authority=42)
print(binary.hex())  # 102a8001
print(len(binary))   # 4 bytes

# With context
binary = uasc.encode("@SENSOR_READ", context={"p0": 5}, domain=1, authority=42)
print(len(binary))   # 8 bytes
```

### Decoding

```python
# Decode binary back to token
token, context = uasc.decode(binary)
print(token)    # @SENSOR_READ
print(context)  # {'p0': 5, 'p1': 0, 'p2': 0, 'p3': 0}

# Execute decoded command
uasc.execute(token, context)
```

### Binary Format

```
Compact format (4 bytes):
  Byte 0: [DDDD][AAAA] - Domain (4 bits) + Authority high (4 bits)
  Byte 1: [AAAA AAAA] - Authority low (8 bits)
  Bytes 2-3: [GGGG GGGG GGGG GGGG] - Glyph code (16 bits)

Extended format (8 bytes):
  Bytes 0-3: Compact format
  Bytes 4-7: Context data (4 x 8-bit parameters)
```

### Use Cases for Binary Encoding

- IoT device communication
- Embedded systems
- Satellite/radio links
- Low-bandwidth networks
- Real-time control systems

---

## HTTP Server API

### Starting the Server

```bash
python uasc_generic.py --server 8420
```

Or programmatically:

```python
from uasc_generic import UASC, create_server

uasc = UASC()
# ... register commands ...

server = create_server(uasc, port=8420)
server.serve_forever()
```

### API Endpoints

#### Execute Command
```bash
POST /exec
Content-Type: application/json

{
    "cmd": "@DEPLOY",
    "inputs": {
        "branch": "main",
        "env": "production"
    }
}
```

Response:
```json
{
    "status": "success",
    "command": "@DEPLOY",
    "duration_ms": 1234,
    "steps": [
        {"name": "git_pull", "status": "success", "duration_ms": 500},
        {"name": "npm_install", "status": "success", "duration_ms": 700}
    ],
    "outputs": {
        "version": "1.2.3"
    },
    "error": null
}
```

#### List Commands
```bash
GET /commands
```

Response:
```json
[
    {
        "token": "@DEPLOY",
        "name": "Deploy",
        "description": "Deploy the application",
        "enabled": true,
        "glyph_code": "0x8001"
    }
]
```

#### Health Check
```bash
GET /health
```

Response:
```json
{"status": "ok"}
```

---

## JSON Profile Format

Commands can be defined in JSON files for easy sharing and version control:

```json
{
    "id": "DEPLOY",
    "name": "Deploy Application",
    "version": 1,
    "description": "Deploy the application to production",
    "author": "devops-team",
    "created": "2025-01-08",

    "inputs": [
        {
            "name": "branch",
            "type": "string",
            "description": "Git branch to deploy",
            "required": false,
            "default": "main"
        },
        {
            "name": "env",
            "type": "string",
            "description": "Target environment",
            "required": true
        }
    ],

    "steps": [
        {
            "name": "checkout",
            "action": "shell",
            "params": {
                "cmd": "git checkout {branch} && git pull"
            }
        },
        {
            "name": "install",
            "action": "shell",
            "params": {
                "cmd": "npm install",
                "timeout": 120
            }
        },
        {
            "name": "build",
            "action": "shell",
            "params": {
                "cmd": "npm run build"
            },
            "condition": "env == 'production'"
        },
        {
            "name": "notify",
            "action": "http",
            "params": {
                "url": "https://slack.com/webhook",
                "method": "POST",
                "body": {"text": "Deployed {branch} to {env}"}
            },
            "continue_on_error": true
        }
    ],

    "on_success": {
        "action": "log",
        "params": {
            "message": "Deployment complete!",
            "level": "info"
        }
    },

    "on_failure": {
        "action": "log",
        "params": {
            "message": "Deployment failed!",
            "level": "error"
        }
    }
}
```

Load with:
```python
uasc.register_from_json("profiles/DEPLOY.json")
```

---

## Real-World Use Cases

### DevOps / CI/CD

| Command | Description |
|---------|-------------|
| `@BUILD` | Compile, test, package |
| `@DEPLOY` | Deploy to servers |
| `@ROLLBACK` | Revert to previous version |
| `@RELEASE` | Tag, build, deploy, notify |

```python
uasc.register("@RELEASE",
    steps=[
        {"action": "shell", "params": {"cmd": "git tag v{version}"}},
        {"action": "shell", "params": {"cmd": "npm run build"}},
        {"action": "shell", "params": {"cmd": "npm publish"}},
        {"action": "http", "params": {"url": "https://slack.com/webhook", "method": "POST", "body": {"text": "Released v{version}!"}}}
    ],
    inputs=[{"name": "version", "required": true}]
)
```

### IoT / Embedded Systems

| Command | Description |
|---------|-------------|
| `@SENSOR_READ` | Read sensor data |
| `@ACTUATOR_SET` | Control actuator |
| `@CALIBRATE` | Run calibration |
| `@DIAGNOSTIC` | System diagnostics |

```python
@uasc.action("read_temperature")
def read_temperature(params, context):
    # Read from sensor
    return {"celsius": 23.5, "fahrenheit": 74.3}

uasc.register("@TEMP_CHECK",
    steps=[
        {"action": "read_temperature", "params": {}, "store_as": "temp"},
        {"action": "log", "params": {"message": "Temperature: {temp}C"}}
    ]
)

# Encode for transmission (4 bytes instead of JSON)
binary = uasc.encode("@TEMP_CHECK")
```

### Workstation Automation

| Command | Description |
|---------|-------------|
| `@WORK` | Open IDE, browser, notes |
| `@MEETING` | Open Zoom, mute notifications |
| `@FOCUS` | Close distractions, start timer |
| `@EOD` | Commit work, close apps, log hours |

```python
uasc.register("@WORK",
    steps=[
        {"action": "shell", "params": {"cmd": "code ."}, "continue_on_error": true},
        {"action": "shell", "params": {"cmd": "start chrome"}, "platform": "windows"},
        {"action": "shell", "params": {"cmd": "open -a 'Google Chrome'"}, "platform": "unix"},
        {"action": "log", "params": {"message": "Workspace ready!"}}
    ]
)
```

### Data Pipelines

| Command | Description |
|---------|-------------|
| `@FETCH` | Download data from sources |
| `@TRANSFORM` | Clean and process data |
| `@VALIDATE` | Check data quality |
| `@EXPORT` | Export to destination |

```python
uasc.register("@ETL_DAILY",
    steps=[
        {"action": "shell", "params": {"cmd": "python fetch_data.py"}, "store_as": "raw_file"},
        {"action": "shell", "params": {"cmd": "python transform.py {raw_file}"}, "store_as": "clean_file"},
        {"action": "shell", "params": {"cmd": "python validate.py {clean_file}"}},
        {"action": "shell", "params": {"cmd": "python upload.py {clean_file}"}},
        {"action": "log", "params": {"message": "ETL complete: {clean_file}"}}
    ]
)
```

### System Administration

| Command | Description |
|---------|-------------|
| `@BACKUP` | Backup databases and files |
| `@CLEANUP` | Remove temp files, logs |
| `@MONITOR` | Check system health |
| `@RESTART` | Restart services |

```python
uasc.register("@BACKUP",
    steps=[
        {"action": "shell", "params": {"cmd": "pg_dump mydb > backup_{date}.sql"}},
        {"action": "shell", "params": {"cmd": "tar -czf backup_{date}.tar.gz /data"}},
        {"action": "shell", "params": {"cmd": "aws s3 cp backup_{date}.tar.gz s3://backups/"}},
        {"action": "log", "params": {"message": "Backup completed: backup_{date}.tar.gz"}}
    ]
)
```

---

## API Reference

### UASC Class

```python
class UASC:
    # Action Registration
    def action(name: str) -> decorator       # Decorator to register action
    def register_action(name: str, handler: Callable)  # Direct registration

    # Command Registration
    def register(token: str, steps: list, ...) -> Command
    def register_from_json(path: str) -> Command
    def register_from_dict(data: dict) -> Command

    # Execution
    def execute(token: str, inputs: dict = None) -> ExecutionResult
    def execute_raw(action: str, params: dict = None) -> Any

    # Utilities
    def list_commands() -> List[dict]
    def list_actions() -> List[str]
    def get_log() -> List[ExecutionResult]
    def clear_log()

    # Binary Encoding
    def encode(token: str, context: dict = None, domain: int = 0, authority: int = 0) -> bytes
    def decode(data: bytes) -> tuple[str, dict]
```

### ExecutionResult Class

```python
@dataclass
class ExecutionResult:
    command: str                    # Command token
    status: str                     # 'success' or 'failed'
    steps: List[StepResult]         # Individual step results
    outputs: Dict[str, Any]         # Stored outputs from steps
    duration_ms: int                # Total execution time
    error: Optional[str]            # Error message if failed
```

### StepResult Class

```python
@dataclass
class StepResult:
    name: str                       # Step name
    status: str                     # 'success', 'failed', or 'skipped'
    output: Any                     # Step output
    error: Optional[str]            # Error message if failed
    duration_ms: int                # Step execution time
```

---

## Running the Demo

```bash
# Run built-in demo
python uasc_generic.py --demo

# Run comprehensive examples
python examples.py

# Start HTTP server
python uasc_generic.py --server 8420
```

---

## Files

| File | Description |
|------|-------------|
| `uasc_generic.py` | Main framework (~500 lines, no dependencies) |
| `examples.py` | 9 comprehensive usage examples |
| `profiles/TEMPLATE.json` | JSON template for creating commands |
| `README.md` | Quick reference |
| `DOCUMENTATION.md` | This file |

---

## Summary

The UASC-M2M Generic Framework is a **programmable command dispatcher** that allows you to:

1. **Define actions** - Reusable functions that do work
2. **Create commands** - Sequences of actions bound to tokens
3. **Execute with inputs** - Run commands with parameters
4. **Chain outputs** - Pass data between steps
5. **Handle errors** - Continue or fail gracefully
6. **Communicate compactly** - 4-8 byte binary encoding
7. **Serve via HTTP** - Remote execution API

It's designed to be simple, extensible, and practical for real-world automation tasks.
