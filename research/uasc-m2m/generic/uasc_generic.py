"""
UASC-M2M Generic Implementation

A simplified, extensible framework for building UASC-M2M applications.
This provides all the core functionality without domain-specific dependencies.

Usage:
    from uasc_generic import UASC, Action, Profile

    # Create instance
    uasc = UASC()

    # Register actions
    @uasc.action("greet")
    def greet(params):
        return f"Hello, {params.get('name', 'World')}!"

    # Register and execute commands
    uasc.register("@HELLO", steps=[
        {"action": "greet", "params": {"name": "{user}"}}
    ])

    result = uasc.execute("@HELLO", {"user": "Alice"})
"""

import subprocess
import json
import time
import platform
import urllib.request
import urllib.error
import hashlib
import struct
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from functools import wraps


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class StepResult:
    """Result of executing a single step."""
    name: str
    status: str  # success, failed, skipped
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ExecutionResult:
    """Result of executing a command."""
    command: str
    status: str  # success, failed
    steps: List[StepResult] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None

    def __repr__(self):
        icon = "OK" if self.status == "success" else "FAIL"
        return f"[{icon}] {self.command} ({self.duration_ms}ms)"


@dataclass
class GlyphFrame:
    """Compact binary representation of a command."""
    domain: int = 0
    authority: int = 0
    glyph_code: int = 0
    context: Optional[Dict[str, Any]] = None

    def to_bytes(self) -> bytes:
        """Encode to compact binary format (4-8 bytes)."""
        packed = (self.domain & 0xF) << 28
        packed |= (self.authority & 0xFFF) << 16
        packed |= (self.glyph_code & 0xFFFF)

        if self.context:
            ctx = self._encode_context()
            return struct.pack('>II', packed, ctx)
        return struct.pack('>I', packed)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'GlyphFrame':
        """Decode from binary format."""
        packed = struct.unpack('>I', data[:4])[0]
        frame = cls(
            domain=(packed >> 28) & 0xF,
            authority=(packed >> 16) & 0xFFF,
            glyph_code=packed & 0xFFFF
        )
        if len(data) >= 8:
            ctx_packed = struct.unpack('>I', data[4:8])[0]
            frame.context = frame._decode_context(ctx_packed)
        return frame

    def _encode_context(self) -> int:
        """Encode context to 32-bit integer."""
        if not self.context:
            return 0
        packed = 0
        for i, (key, value) in enumerate(list(self.context.items())[:4]):
            if isinstance(value, int):
                packed |= (value & 0xFF) << (24 - i * 8)
        return packed

    def _decode_context(self, packed: int) -> Dict[str, Any]:
        """Decode 32-bit integer to context."""
        return {
            'p0': (packed >> 24) & 0xFF,
            'p1': (packed >> 16) & 0xFF,
            'p2': (packed >> 8) & 0xFF,
            'p3': packed & 0xFF
        }


# ============================================================================
# ACTION REGISTRY - Register custom functions
# ============================================================================

class ActionRegistry:
    """Registry for action handlers."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in actions."""
        self.register("shell", self._action_shell)
        self.register("http", self._action_http)
        self.register("log", self._action_log)
        self.register("set", self._action_set)
        self.register("wait", self._action_wait)
        self.register("python", self._action_python)

    def register(self, name: str, handler: Callable):
        """Register an action handler."""
        self._handlers[name] = handler

    def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute an action."""
        if action not in self._handlers:
            raise ValueError(f"Unknown action: {action}")
        return self._handlers[action](params, context)

    def has(self, action: str) -> bool:
        """Check if action exists."""
        return action in self._handlers

    def list(self) -> List[str]:
        """List all registered actions."""
        return list(self._handlers.keys())

    # Built-in actions
    def _action_shell(self, params: Dict, context: Dict) -> str:
        """Execute shell command."""
        cmd = params.get('cmd', '')
        timeout = params.get('timeout', 60)
        cwd = params.get('cwd', '.')

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )

        output = result.stdout
        if result.stderr:
            output += '\n' + result.stderr

        if result.returncode != 0 and not params.get('ignore_error'):
            raise RuntimeError(f"Command failed (exit {result.returncode}): {output}")

        return output.strip()

    def _action_http(self, params: Dict, context: Dict) -> str:
        """Make HTTP request."""
        url = params.get('url', '')
        method = params.get('method', 'GET')
        body = params.get('body')
        headers = params.get('headers', {})
        timeout = params.get('timeout', 30)

        data = json.dumps(body).encode() if body else None

        if data and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=data, method=method, headers=headers)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()

    def _action_log(self, params: Dict, context: Dict) -> str:
        """Log a message."""
        message = params.get('message', '')
        level = params.get('level', 'info').upper()
        print(f"[{level}] {message}")
        return message

    def _action_set(self, params: Dict, context: Dict) -> Any:
        """Set a variable."""
        name = params.get('name')
        value = params.get('value')
        if name:
            context['vars'][name] = value
        return value

    def _action_wait(self, params: Dict, context: Dict) -> None:
        """Wait for specified seconds."""
        seconds = params.get('seconds', 1)
        time.sleep(seconds)

    def _action_python(self, params: Dict, context: Dict) -> Any:
        """Execute Python code (use with caution)."""
        code = params.get('code', '')
        local_vars = {'params': params, 'context': context, 'result': None}
        exec(code, {}, local_vars)
        return local_vars.get('result')


# ============================================================================
# COMMAND REGISTRY - Map tokens to execution profiles
# ============================================================================

@dataclass
class Command:
    """A registered command with its execution profile."""
    token: str
    name: str
    description: str
    steps: List[Dict[str, Any]]
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    on_success: Optional[Dict] = None
    on_failure: Optional[Dict] = None
    glyph_code: int = 0
    enabled: bool = True


class CommandRegistry:
    """Registry for commands and their execution profiles."""

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._next_glyph = 0x8001

    def register(
        self,
        token: str,
        steps: List[Dict[str, Any]],
        name: str = None,
        description: str = "",
        inputs: List[Dict[str, Any]] = None,
        on_success: Dict = None,
        on_failure: Dict = None
    ) -> Command:
        """Register a command."""
        if not token.startswith('@'):
            token = '@' + token

        cmd = Command(
            token=token,
            name=name or token[1:],
            description=description,
            steps=steps,
            inputs=inputs or [],
            on_success=on_success,
            on_failure=on_failure,
            glyph_code=self._next_glyph
        )

        self._commands[token] = cmd
        self._next_glyph += 1

        return cmd

    def get(self, token: str) -> Optional[Command]:
        """Get a command by token."""
        if not token.startswith('@'):
            token = '@' + token
        return self._commands.get(token)

    def list(self) -> List[Command]:
        """List all registered commands."""
        return list(self._commands.values())

    def enable(self, token: str, enabled: bool = True):
        """Enable or disable a command."""
        cmd = self.get(token)
        if cmd:
            cmd.enabled = enabled

    def remove(self, token: str):
        """Remove a command."""
        if not token.startswith('@'):
            token = '@' + token
        self._commands.pop(token, None)


# ============================================================================
# EXECUTOR - Execute command steps
# ============================================================================

class Executor:
    """Executes command steps."""

    def __init__(self, actions: ActionRegistry):
        self.actions = actions
        self.platform = 'windows' if platform.system() == 'Windows' else 'unix'

    def execute(self, command: Command, inputs: Dict[str, Any] = None) -> ExecutionResult:
        """Execute a command."""
        start_time = time.time()

        # Build context
        context = {
            'vars': {
                'timestamp': datetime.now().isoformat(),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'platform': self.platform,
                'command': command.token
            }
        }

        # Apply inputs
        if inputs:
            context['vars'].update(inputs)

        # Apply input defaults
        for input_def in command.inputs:
            name = input_def['name']
            if name not in context['vars'] and 'default' in input_def:
                context['vars'][name] = input_def['default']

        result = ExecutionResult(
            command=command.token,
            status='success'
        )

        # Execute steps
        for step in command.steps:
            step_result = self._execute_step(step, context)
            result.steps.append(step_result)

            # Store output
            if step.get('store_as') and step_result.output is not None:
                context['vars'][step['store_as']] = step_result.output
                result.outputs[step['store_as']] = step_result.output

            # Check failure
            if step_result.status == 'failed':
                if not step.get('continue_on_error'):
                    result.status = 'failed'
                    result.error = f"Step '{step_result.name}' failed: {step_result.error}"
                    break

        result.duration_ms = int((time.time() - start_time) * 1000)

        # Run success/failure handler
        handler = command.on_success if result.status == 'success' else command.on_failure
        if handler:
            self._execute_step(handler, context)

        return result

    def _execute_step(self, step: Dict, context: Dict) -> StepResult:
        """Execute a single step."""
        name = step.get('name', 'unnamed')
        action = step.get('action', step.get('type', 'shell'))

        # Platform filter
        step_platform = step.get('platform')
        if step_platform and step_platform != self.platform:
            return StepResult(name=name, status='skipped', output='Platform mismatch')

        # Condition filter
        condition = step.get('condition')
        if condition and not self._evaluate_condition(condition, context):
            return StepResult(name=name, status='skipped', output='Condition not met')

        start_time = time.time()

        try:
            # Interpolate params
            params = self._interpolate_params(step.get('params', step), context)

            # Execute action
            output = self.actions.execute(action, params, context)

            return StepResult(
                name=name,
                status='success',
                output=output,
                duration_ms=int((time.time() - start_time) * 1000)
            )

        except Exception as e:
            return StepResult(
                name=name,
                status='failed',
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _interpolate_params(self, params: Dict, context: Dict) -> Dict:
        """Replace {variable} placeholders."""
        if not isinstance(params, dict):
            return params

        result = {}
        for key, value in params.items():
            if key in ('action', 'type', 'name', 'condition', 'platform', 'store_as', 'continue_on_error'):
                continue
            if isinstance(value, str):
                for var_name, var_value in context['vars'].items():
                    value = value.replace(f'{{{var_name}}}', str(var_value))
            result[key] = value
        return result

    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """Evaluate a condition expression."""
        condition = condition.strip()

        if condition.lower() == 'true':
            return True
        if condition.lower() == 'false':
            return False

        # Handle comparisons
        for op, func in [('!=', lambda a, b: a != b), ('==', lambda a, b: a == b)]:
            if op in condition:
                parts = condition.split(op)
                if len(parts) == 2:
                    var_name = parts[0].strip()
                    expected = parts[1].strip().strip("'\"")
                    actual = str(context['vars'].get(var_name, ''))
                    return func(actual, expected)

        # Boolean variable
        if condition in context['vars']:
            return bool(context['vars'][condition])

        return False


# ============================================================================
# MAIN UASC CLASS - Simple unified interface
# ============================================================================

class UASC:
    """
    UASC-M2M Generic Framework

    Simple, extensible interface for command execution.

    Example:
        uasc = UASC()

        # Register custom action
        @uasc.action("notify")
        def notify(params, context):
            print(f"NOTIFICATION: {params['message']}")
            return True

        # Register command
        uasc.register("@HELLO",
            steps=[
                {"action": "log", "params": {"message": "Hello {name}!"}},
                {"action": "notify", "params": {"message": "Greeted {name}"}}
            ],
            inputs=[{"name": "name", "default": "World"}]
        )

        # Execute
        result = uasc.execute("@HELLO", {"name": "Alice"})
    """

    def __init__(self):
        self.actions = ActionRegistry()
        self.commands = CommandRegistry()
        self.executor = Executor(self.actions)
        self._execution_log: List[ExecutionResult] = []

    # === Action Registration ===

    def action(self, name: str = None):
        """Decorator to register an action handler."""
        def decorator(func: Callable):
            action_name = name or func.__name__

            @wraps(func)
            def wrapper(params: Dict, context: Dict):
                return func(params, context)

            self.actions.register(action_name, wrapper)
            return func
        return decorator

    def register_action(self, name: str, handler: Callable):
        """Register an action handler directly."""
        self.actions.register(name, handler)

    # === Command Registration ===

    def register(
        self,
        token: str,
        steps: List[Dict[str, Any]],
        name: str = None,
        description: str = "",
        inputs: List[Dict[str, Any]] = None,
        on_success: Dict = None,
        on_failure: Dict = None
    ) -> Command:
        """Register a command."""
        return self.commands.register(
            token=token,
            steps=steps,
            name=name,
            description=description,
            inputs=inputs,
            on_success=on_success,
            on_failure=on_failure
        )

    def register_from_json(self, json_path: str) -> Command:
        """Register command from JSON file."""
        with open(json_path, 'r') as f:
            data = json.load(f)

        return self.register(
            token=f"@{data['id']}",
            steps=data.get('steps', []),
            name=data.get('name', data['id']),
            description=data.get('description', ''),
            inputs=data.get('inputs', []),
            on_success=data.get('on_success'),
            on_failure=data.get('on_failure')
        )

    def register_from_dict(self, data: Dict[str, Any]) -> Command:
        """Register command from dictionary."""
        return self.register(
            token=f"@{data['id']}",
            steps=data.get('steps', []),
            name=data.get('name', data['id']),
            description=data.get('description', ''),
            inputs=data.get('inputs', []),
            on_success=data.get('on_success'),
            on_failure=data.get('on_failure')
        )

    # === Execution ===

    def execute(self, token: str, inputs: Dict[str, Any] = None) -> ExecutionResult:
        """Execute a command by token."""
        command = self.commands.get(token)
        if not command:
            return ExecutionResult(
                command=token,
                status='failed',
                error=f"Unknown command: {token}"
            )

        if not command.enabled:
            return ExecutionResult(
                command=token,
                status='failed',
                error=f"Command disabled: {token}"
            )

        result = self.executor.execute(command, inputs)
        self._execution_log.append(result)
        return result

    def execute_raw(self, action: str, params: Dict[str, Any] = None) -> Any:
        """Execute a single action directly."""
        context = {'vars': {}}
        return self.actions.execute(action, params or {}, context)

    # === Utilities ===

    def list_commands(self) -> List[Dict[str, Any]]:
        """List all registered commands."""
        return [
            {
                'token': cmd.token,
                'name': cmd.name,
                'description': cmd.description,
                'enabled': cmd.enabled,
                'glyph_code': f"0x{cmd.glyph_code:04X}"
            }
            for cmd in self.commands.list()
        ]

    def list_actions(self) -> List[str]:
        """List all registered actions."""
        return self.actions.list()

    def get_log(self) -> List[ExecutionResult]:
        """Get execution log."""
        return self._execution_log.copy()

    def clear_log(self):
        """Clear execution log."""
        self._execution_log.clear()

    # === Binary Encoding (for M2M transmission) ===

    def encode(self, token: str, context: Dict = None, domain: int = 0, authority: int = 0) -> bytes:
        """Encode command to compact binary format."""
        command = self.commands.get(token)
        if not command:
            raise ValueError(f"Unknown command: {token}")

        frame = GlyphFrame(
            domain=domain,
            authority=authority,
            glyph_code=command.glyph_code,
            context=context
        )
        return frame.to_bytes()

    def decode(self, data: bytes) -> tuple:
        """Decode binary to (token, context)."""
        frame = GlyphFrame.from_bytes(data)

        # Find command by glyph code
        for cmd in self.commands.list():
            if cmd.glyph_code == frame.glyph_code:
                return cmd.token, frame.context

        return None, frame.context


# ============================================================================
# HTTP SERVER - Simple API server
# ============================================================================

def create_server(uasc: UASC, port: int = 8420):
    """Create a simple HTTP server for the UASC instance."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == '/exec':
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length)) if length else {}

                token = body.get('cmd', '')
                inputs = body.get('inputs', {})

                result = uasc.execute(token, inputs)

                response = {
                    'status': result.status,
                    'command': result.command,
                    'duration_ms': result.duration_ms,
                    'steps': [
                        {'name': s.name, 'status': s.status, 'duration_ms': s.duration_ms}
                        for s in result.steps
                    ],
                    'outputs': result.outputs,
                    'error': result.error
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_error(404)

        def do_GET(self):
            if self.path == '/commands':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(uasc.list_commands()).encode())
            elif self.path == '/health':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            print(f"[SERVER] {args[0]}")

    server = HTTPServer(('', port), Handler)
    print(f"UASC Server running on http://localhost:{port}")
    print(f"  POST /exec    - Execute command")
    print(f"  GET  /commands - List commands")
    print(f"  GET  /health   - Health check")
    return server


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Command-line interface."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python uasc_generic.py <command> [args...]")
        print("       python uasc_generic.py --server [port]")
        print("       python uasc_generic.py --demo")
        return

    if sys.argv[1] == '--demo':
        run_demo()
    elif sys.argv[1] == '--server':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8420
        uasc = UASC()
        # Load example commands
        _register_example_commands(uasc)
        server = create_server(uasc, port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
    else:
        print(f"Unknown command: {sys.argv[1]}")


def _register_example_commands(uasc: UASC):
    """Register example commands."""
    uasc.register("@HELLO",
        steps=[
            {"action": "log", "params": {"message": "Hello, {name}!"}}
        ],
        inputs=[{"name": "name", "default": "World"}],
        description="Simple greeting"
    )

    uasc.register("@STATUS",
        steps=[
            {"action": "shell", "params": {"cmd": "echo Platform: {platform}"}},
            {"action": "shell", "params": {"cmd": "date /t"}, "platform": "windows"},
            {"action": "shell", "params": {"cmd": "date"}, "platform": "unix"},
        ],
        description="Show system status"
    )


def run_demo():
    """Run demonstration."""
    print("=" * 60)
    print("  UASC-M2M Generic Framework Demo")
    print("=" * 60)

    # Create instance
    uasc = UASC()

    # Register custom action
    @uasc.action("greet")
    def greet(params, context):
        name = params.get('name', 'World')
        return f"Hello, {name}!"

    @uasc.action("calculate")
    def calculate(params, context):
        a = params.get('a', 0)
        b = params.get('b', 0)
        op = params.get('op', 'add')
        if op == 'add':
            return a + b
        elif op == 'multiply':
            return a * b
        return 0

    print("\n[1] Registered custom actions: greet, calculate")
    print(f"    Available actions: {uasc.list_actions()}")

    # Register commands
    uasc.register("@GREET",
        steps=[
            {"action": "greet", "params": {"name": "{user}"}, "store_as": "greeting"},
            {"action": "log", "params": {"message": "Greeting: {greeting}"}}
        ],
        inputs=[{"name": "user", "default": "World"}],
        description="Greet a user"
    )

    uasc.register("@MATH",
        steps=[
            {"action": "calculate", "params": {"a": 10, "b": 5, "op": "add"}, "store_as": "sum"},
            {"action": "calculate", "params": {"a": 10, "b": 5, "op": "multiply"}, "store_as": "product"},
            {"action": "log", "params": {"message": "10 + 5 = {sum}, 10 * 5 = {product}"}}
        ],
        description="Math demonstration"
    )

    uasc.register("@SYSINFO",
        steps=[
            {"action": "shell", "params": {"cmd": "hostname"}, "store_as": "hostname"},
            {"action": "shell", "params": {"cmd": "whoami"}, "store_as": "user"},
            {"action": "log", "params": {"message": "Host: {hostname}, User: {user}"}}
        ],
        description="Get system info"
    )

    print("\n[2] Registered commands:")
    for cmd in uasc.list_commands():
        print(f"    {cmd['token']:12} - {cmd['description']}")

    # Execute commands
    print("\n[3] Executing commands:")

    print("\n    --- @GREET ---")
    result = uasc.execute("@GREET", {"user": "Alice"})
    print(f"    {result}")
    print(f"    Outputs: {result.outputs}")

    print("\n    --- @MATH ---")
    result = uasc.execute("@MATH")
    print(f"    {result}")
    print(f"    Outputs: {result.outputs}")

    print("\n    --- @SYSINFO ---")
    result = uasc.execute("@SYSINFO")
    print(f"    {result}")
    print(f"    Outputs: {result.outputs}")

    # Binary encoding
    print("\n[4] Binary encoding demo:")
    binary = uasc.encode("@GREET", {"p0": 1})
    print(f"    @GREET encoded: {binary.hex()} ({len(binary)} bytes)")

    token, ctx = uasc.decode(binary)
    print(f"    Decoded: token={token}, context={ctx}")

    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
