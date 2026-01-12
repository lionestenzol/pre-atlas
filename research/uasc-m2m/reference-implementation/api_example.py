#!/usr/bin/env python3
"""
UASC-M2M API Example
====================

Demonstrates how UASC works as a control-plane layer for APIs.

Traditional API:
    POST /api/emergency/clear-corridor
    {
        "zone": 5,
        "vehicle_id": "AMB-001",
        "priority": 5,
        "mode": "emergency",
        "timeout": 30,
        "notify": ["dispatch", "hospital"],
        ...
    }

UASC API:
    POST /exec
    { "cmd": "@C3", "zone": 5 }

The server holds all execution logic. The client sends only addresses.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

from core.glyph import GlyphFrame, Domain
from core.registry import Registry, ExecutionGraph
from core.trust import create_mock_trust_chain
from core.interpreter import Interpreter, ActionRegistry
from actions.traffic_control import register_traffic_actions


# Token to glyph code mapping
TOKEN_MAP = {
    '@C3': 0x8003,   # Emergency control
    '@N4': 0x8004,   # Network optimization
    '@A1': 0x8001,   # Sequential execution
}


def create_emergency_graph() -> ExecutionGraph:
    """Emergency vehicle priority graph."""
    return ExecutionGraph(
        graph_id="emergency-priority-001",
        name="emergency_vehicle_priority",
        version="1.0.0",
        domain="smart_city",
        inputs=[
            {"name": "zone", "type": "integer", "required": True},
            {"name": "vehicle_id", "type": "string", "default": "UNIT-001"},
            {"name": "priority", "type": "integer", "default": 5}
        ],
        outputs=[
            {"name": "corridor_cleared", "type": "boolean"},
            {"name": "signals_affected", "type": "integer"}
        ],
        nodes={
            "start": {"type": "entry", "next": "clear_corridor"},
            "clear_corridor": {
                "type": "action",
                "operation": "traffic.emergency_corridor",
                "params": {"zone": "inputs.zone", "vehicle_id": "inputs.vehicle_id"},
                "next": "success"
            },
            "success": {
                "type": "exit",
                "outputs": {
                    "corridor_cleared": True,
                    "signals_affected": "clear_corridor.signal_count"
                }
            }
        }
    )


def create_optimization_graph() -> ExecutionGraph:
    """Zone optimization graph."""
    return ExecutionGraph(
        graph_id="zone-optimization-001",
        name="zone_optimization",
        version="1.0.0",
        domain="smart_city",
        inputs=[{"name": "zone", "type": "integer", "required": True}],
        outputs=[{"name": "status", "type": "string"}],
        nodes={
            "start": {"type": "entry", "next": "optimize"},
            "optimize": {
                "type": "action",
                "operation": "traffic.optimize_route",
                "params": {"zone": "inputs.zone"},
                "next": "success"
            },
            "success": {
                "type": "exit",
                "outputs": {"status": "optimized", "improvement": "optimize.improvement_percent"}
            }
        }
    )


class UASCServer:
    """UASC execution server."""

    def __init__(self):
        # Initialize registry
        self.registry = Registry(
            registry_id="api-server-001",
            domain=Domain.SMART_CITY,
            authority=0x042
        )

        # Register execution graphs
        self.registry.register_graph(create_emergency_graph())
        self.registry.register_graph(create_optimization_graph())

        # Bind tokens to graphs
        self.registry.bind_glyph(0x8003, "emergency-priority-001")
        self.registry.bind_glyph(0x8004, "zone-optimization-001")

        # Setup trust
        self.trust = create_mock_trust_chain(
            domain=Domain.SMART_CITY,
            authority=0x042,
            authority_name="API Server"
        )

        # Setup actions
        self.actions = ActionRegistry()
        register_traffic_actions(self.actions)

        # Create interpreter
        self.interpreter = Interpreter(
            registry=self.registry,
            trust_verifier=self.trust,
            action_registry=self.actions
        )

    def execute(self, cmd: str, context: dict) -> dict:
        """Execute a UASC command."""
        # Resolve token to glyph code
        glyph_code = TOKEN_MAP.get(cmd)
        if not glyph_code:
            return {"error": f"Unknown command: {cmd}", "status": "rejected"}

        # Build frame
        frame = GlyphFrame(
            domain=Domain.SMART_CITY,
            authority=0x042,
            glyph_code=glyph_code,
            context=context
        )

        # Execute
        result = self.interpreter.execute(frame)

        return {
            "status": result.status,
            "outputs": result.outputs,
            "execution_time_ms": result.execution_time_ms,
            "trace": result.node_trace,
            "error": result.error
        }


# Global server instance
uasc_server = UASCServer()


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for UASC API."""

    def do_POST(self):
        if self.path == '/exec':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
                cmd = data.get('cmd', '')
                context = {k: v for k, v in data.items() if k != 'cmd'}

                # Execute UASC command
                result = uasc_server.execute(cmd, context)

                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=2).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"  [{self.address_string()}] {args[0]}")


def demo_without_server():
    """Demonstrate UASC API pattern without running HTTP server."""
    print("=" * 70)
    print("  UASC API Pattern Demo")
    print("  Command-Address Control Layer")
    print("=" * 70)

    print("\n[1] Traditional API Call (what apps typically send):")
    print("-" * 50)
    traditional = {
        "command": "emergency_vehicle_priority",
        "domain": "smart_city",
        "authority": "city_of_tokyo",
        "parameters": {
            "zone": 5,
            "vehicle_id": "AMB-001",
            "priority": 5,
            "mode": "emergency",
            "clear_intersections": True,
            "notify_dispatch": True,
            "timeout_seconds": 30
        },
        "authentication": {"token": "...", "signature": "..."}
    }
    print(f"  POST /api/emergency/clear-corridor")
    print(f"  Body: {len(json.dumps(traditional))} bytes")
    print(f"  {json.dumps(traditional, indent=4)[:200]}...")

    print("\n[2] UASC API Call (what apps should send):")
    print("-" * 50)
    uasc_request = {"cmd": "@C3", "zone": 5}
    print(f"  POST /exec")
    print(f"  Body: {len(json.dumps(uasc_request))} bytes")
    print(f"  {json.dumps(uasc_request)}")

    print("\n[3] Server executes stored execution profile:")
    print("-" * 50)
    result = uasc_server.execute("@C3", {"zone": 5})
    print(f"  Command: @C3")
    print(f"  Resolved to: emergency_vehicle_priority graph")
    print(f"  Execution trace: {' -> '.join(result['trace'])}")
    print(f"  Result: {result['status'].upper()}")
    print(f"  Outputs: {result['outputs']}")

    print("\n[4] Another command - Zone Optimization:")
    print("-" * 50)
    result2 = uasc_server.execute("@N4", {"zone": 8})
    print(f"  Command: @N4")
    print(f"  Resolved to: zone_optimization graph")
    print(f"  Execution trace: {' -> '.join(result2['trace'])}")
    print(f"  Result: {result2['status'].upper()}")
    print(f"  Outputs: {result2['outputs']}")

    print("\n[5] Comparison:")
    print("-" * 50)
    print(f"  Traditional request size: {len(json.dumps(traditional))} bytes")
    print(f"  UASC request size: {len(json.dumps(uasc_request))} bytes")
    print(f"  Reduction: {len(json.dumps(traditional)) / len(json.dumps(uasc_request)):.1f}x smaller")

    print("\n" + "=" * 70)
    print("  KEY INSIGHT")
    print("=" * 70)
    print("""
  The client sends ONLY command addresses.

  All logic, workflows, and behavior live in versioned
  execution profiles on the server.

  This is a control-plane architecture:
    - Deterministic
    - Auditable
    - Versionable
    - Safe for AI automation
    - Ultra-low bandwidth

  Same pattern as: kernels, PLCs, CAN bus, avionics
  Now available for: APIs, microservices, AI orchestration
""")


def run_server(port=8080):
    """Run UASC HTTP server."""
    print(f"\nStarting UASC API server on port {port}...")
    print(f"Try: curl -X POST http://localhost:{port}/exec -d '{{\"cmd\":\"@C3\",\"zone\":5}}'")
    server = HTTPServer(('localhost', port), RequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--serve':
        run_server()
    else:
        demo_without_server()
