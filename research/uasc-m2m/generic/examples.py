"""
UASC-M2M Generic Framework - Examples

This file demonstrates various ways to use the generic UASC framework.
Run: python examples.py
"""

from uasc_generic import UASC, ExecutionResult
import json


def example_1_basic_usage():
    """Basic usage - register and execute commands."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)

    uasc = UASC()

    # Register a simple command using built-in actions
    uasc.register("@HELLO",
        steps=[
            {"action": "log", "params": {"message": "Hello, {name}!"}},
            {"action": "log", "params": {"message": "Welcome to UASC-M2M"}}
        ],
        inputs=[{"name": "name", "default": "World"}],
        description="Simple greeting command"
    )

    # Execute
    result = uasc.execute("@HELLO", {"name": "Developer"})
    print(f"\nResult: {result}")


def example_2_custom_actions():
    """Register custom action handlers."""
    print("\n" + "=" * 60)
    print("Example 2: Custom Actions")
    print("=" * 60)

    uasc = UASC()

    # Method 1: Decorator
    @uasc.action("reverse")
    def reverse_string(params, context):
        text = params.get('text', '')
        return text[::-1]

    # Method 2: Direct registration
    def uppercase(params, context):
        text = params.get('text', '')
        return text.upper()

    uasc.register_action("uppercase", uppercase)

    # Use in command
    uasc.register("@TRANSFORM",
        steps=[
            {"action": "reverse", "params": {"text": "{input}"}, "store_as": "reversed"},
            {"action": "uppercase", "params": {"text": "{reversed}"}, "store_as": "final"},
            {"action": "log", "params": {"message": "Result: {final}"}}
        ],
        inputs=[{"name": "input", "default": "hello"}]
    )

    result = uasc.execute("@TRANSFORM", {"input": "hello world"})
    print(f"\nResult: {result}")
    print(f"Outputs: {result.outputs}")


def example_3_conditional_execution():
    """Conditional and platform-specific execution."""
    print("\n" + "=" * 60)
    print("Example 3: Conditional Execution")
    print("=" * 60)

    uasc = UASC()

    uasc.register("@PLATFORM_INFO",
        steps=[
            # Always runs
            {"action": "log", "params": {"message": "Platform: {platform}"}},

            # Windows only
            {
                "name": "win_info",
                "action": "shell",
                "params": {"cmd": "ver"},
                "platform": "windows",
                "store_as": "os_version"
            },

            # Unix only
            {
                "name": "unix_info",
                "action": "shell",
                "params": {"cmd": "uname -a"},
                "platform": "unix",
                "store_as": "os_version"
            },

            # Conditional based on input
            {
                "name": "detailed_info",
                "action": "shell",
                "params": {"cmd": "systeminfo"},
                "platform": "windows",
                "condition": "detailed == 'yes'"
            }
        ],
        inputs=[{"name": "detailed", "default": "no"}]
    )

    result = uasc.execute("@PLATFORM_INFO")
    print(f"\nResult: {result}")


def example_4_chained_operations():
    """Chain multiple operations with output passing."""
    print("\n" + "=" * 60)
    print("Example 4: Chained Operations")
    print("=" * 60)

    uasc = UASC()

    @uasc.action("fetch_data")
    def fetch_data(params, context):
        # Simulate fetching data
        return {"items": [1, 2, 3, 4, 5], "count": 5}

    @uasc.action("process_data")
    def process_data(params, context):
        # Get data from context (set by previous step)
        data = context['vars'].get('raw_data', {})
        if isinstance(data, str):
            data = json.loads(data) if data.startswith('{') else {"items": []}
        items = data.get('items', [])
        return {"sum": sum(items), "avg": sum(items) / len(items) if items else 0}

    @uasc.action("report")
    def report(params, context):
        stats = context['vars'].get('stats', {})
        return f"Sum: {stats.get('sum', 0)}, Average: {stats.get('avg', 0)}"

    uasc.register("@PIPELINE",
        steps=[
            {"action": "log", "params": {"message": "Starting data pipeline..."}},
            {"action": "fetch_data", "params": {}, "store_as": "raw_data"},
            {"action": "process_data", "params": {}, "store_as": "stats"},
            {"action": "report", "params": {}, "store_as": "report"},
            {"action": "log", "params": {"message": "Report: {report}"}}
        ],
        description="Data processing pipeline"
    )

    result = uasc.execute("@PIPELINE")
    print(f"\nResult: {result}")
    print(f"Stats: {result.outputs.get('stats')}")


def example_5_error_handling():
    """Error handling and continue_on_error."""
    print("\n" + "=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)

    uasc = UASC()

    @uasc.action("maybe_fail")
    def maybe_fail(params, context):
        if params.get('should_fail'):
            raise RuntimeError("Intentional failure!")
        return "Success!"

    uasc.register("@ROBUST",
        steps=[
            {"action": "log", "params": {"message": "Step 1: Starting..."}},
            {
                "name": "risky_step",
                "action": "maybe_fail",
                "params": {"should_fail": True},
                "continue_on_error": True  # Continue even if this fails
            },
            {"action": "log", "params": {"message": "Step 3: This still runs!"}},
            {
                "name": "safe_step",
                "action": "maybe_fail",
                "params": {"should_fail": False},
                "store_as": "result"
            }
        ],
        on_success={"action": "log", "params": {"message": "All done!", "level": "info"}},
        on_failure={"action": "log", "params": {"message": "Something failed!", "level": "error"}}
    )

    result = uasc.execute("@ROBUST")
    print(f"\nResult: {result}")
    for step in result.steps:
        icon = "OK" if step.status == "success" else "FAIL" if step.status == "failed" else "SKIP"
        print(f"  [{icon}] {step.name}: {step.status}")


def example_6_load_from_json():
    """Load command from JSON file."""
    print("\n" + "=" * 60)
    print("Example 6: Load from JSON")
    print("=" * 60)

    uasc = UASC()

    # Create a command definition as dict (simulating JSON)
    command_def = {
        "id": "BACKUP",
        "description": "Backup important files",
        "inputs": [
            {"name": "source", "default": "."},
            {"name": "dest", "default": "./backup"}
        ],
        "steps": [
            {"action": "log", "params": {"message": "Backing up {source} to {dest}"}},
            {
                "action": "shell",
                "params": {"cmd": "echo Would backup from {source} to {dest}"},
                "store_as": "backup_result"
            },
            {"action": "log", "params": {"message": "Backup complete!"}}
        ]
    }

    # Register from dict
    uasc.register_from_dict(command_def)

    # Execute
    result = uasc.execute("@BACKUP", {"source": "/data", "dest": "/backup"})
    print(f"\nResult: {result}")


def example_7_binary_encoding():
    """Binary encoding for M2M communication."""
    print("\n" + "=" * 60)
    print("Example 7: Binary Encoding")
    print("=" * 60)

    uasc = UASC()

    uasc.register("@SENSOR_READ",
        steps=[{"action": "log", "params": {"message": "Reading sensor..."}}],
        description="Read sensor data"
    )

    uasc.register("@ACTUATOR_SET",
        steps=[{"action": "log", "params": {"message": "Setting actuator..."}}],
        description="Set actuator value"
    )

    # Encode commands to binary
    print("\nEncoding commands to binary:")

    for token in ["@SENSOR_READ", "@ACTUATOR_SET"]:
        binary = uasc.encode(token, domain=1, authority=42)
        decoded_token, _ = uasc.decode(binary)
        print(f"  {token}:")
        print(f"    Binary: {binary.hex()}")
        print(f"    Size: {len(binary)} bytes")
        print(f"    Decoded: {decoded_token}")


def example_8_http_server():
    """Start HTTP server (non-blocking demo)."""
    print("\n" + "=" * 60)
    print("Example 8: HTTP Server")
    print("=" * 60)

    print("""
To start the HTTP server, run:

    python uasc_generic.py --server 8420

Then use curl or any HTTP client:

    # List commands
    curl http://localhost:8420/commands

    # Execute command
    curl -X POST http://localhost:8420/exec \\
         -H "Content-Type: application/json" \\
         -d '{"cmd": "@HELLO", "inputs": {"name": "API User"}}'

    # Health check
    curl http://localhost:8420/health
""")


def example_9_real_world_automation():
    """Real-world automation example."""
    print("\n" + "=" * 60)
    print("Example 9: Real-World Automation")
    print("=" * 60)

    uasc = UASC()

    # Git workflow automation
    uasc.register("@GIT_STATUS",
        steps=[
            {"action": "shell", "params": {"cmd": "git status --short"}, "store_as": "status"},
            {"action": "shell", "params": {"cmd": "git branch --show-current"}, "store_as": "branch"},
            {"action": "log", "params": {"message": "Branch: {branch}\nStatus:\n{status}"}}
        ],
        description="Show git status"
    )

    # Development environment
    uasc.register("@DEV_START",
        steps=[
            {"action": "log", "params": {"message": "Starting development environment..."}},
            {
                "action": "shell",
                "params": {"cmd": "code ."},
                "continue_on_error": True
            },
            {"action": "log", "params": {"message": "Environment ready!"}}
        ],
        description="Start development environment"
    )

    print("\nRegistered real-world commands:")
    for cmd in uasc.list_commands():
        print(f"  {cmd['token']:15} - {cmd['description']}")

    # Execute git status
    result = uasc.execute("@GIT_STATUS")
    print(f"\nGit Status Result: {result}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("  UASC-M2M Generic Framework Examples")
    print("=" * 60)

    examples = [
        example_1_basic_usage,
        example_2_custom_actions,
        example_3_conditional_execution,
        example_4_chained_operations,
        example_5_error_handling,
        example_6_load_from_json,
        example_7_binary_encoding,
        example_8_http_server,
        example_9_real_world_automation,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\nError in {example.__name__}: {e}")

    print("\n" + "=" * 60)
    print("  All Examples Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
