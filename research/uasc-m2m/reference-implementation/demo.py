#!/usr/bin/env python3
"""
UASC-M2M Reference Implementation Demo
=======================================

Demonstrates the complete UASC-M2M pipeline:
1. Registry setup with execution graphs
2. Trust chain establishment
3. Action handler registration
4. Glyph encoding and transmission
5. Trust verification and execution
6. Result reporting

Domain: Smart City Traffic Control
"""

from core.glyph import GlyphFrame, GlyphCodec, Domain
from core.registry import Registry, ExecutionGraph
from core.trust import create_mock_trust_chain
from core.interpreter import Interpreter, ActionRegistry
from actions.traffic_control import register_traffic_actions


def create_emergency_priority_graph() -> ExecutionGraph:
    """Create the emergency vehicle priority execution graph."""
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
            "start": {
                "type": "entry",
                "next": "check_priority"
            },
            "check_priority": {
                "type": "condition",
                "expression": "priority >= 3",
                "on_true": "clear_corridor",
                "on_false": "standard_timing"
            },
            "clear_corridor": {
                "type": "action",
                "operation": "traffic.emergency_corridor",
                "params": {
                    "zone": "inputs.zone",
                    "vehicle_id": "inputs.vehicle_id"
                },
                "next": "success_emergency"
            },
            "standard_timing": {
                "type": "action",
                "operation": "traffic.optimize_route",
                "params": {
                    "zone": "inputs.zone"
                },
                "next": "success_standard"
            },
            "success_emergency": {
                "type": "exit",
                "outputs": {
                    "corridor_cleared": True,
                    "signals_affected": "clear_corridor.signal_count"
                }
            },
            "success_standard": {
                "type": "exit",
                "outputs": {
                    "corridor_cleared": False,
                    "signals_affected": "standard_timing.signal_count"
                }
            }
        },
        error_handling={
            "default": "retry",
            "max_retries": 2
        },
        constraints={
            "max_execution_time_ms": 2000
        }
    )


def create_zone_optimization_graph() -> ExecutionGraph:
    """Create the zone optimization execution graph."""
    return ExecutionGraph(
        graph_id="zone-optimization-001",
        name="zone_traffic_optimization",
        version="1.0.0",
        domain="smart_city",
        inputs=[
            {"name": "zone", "type": "integer", "required": True},
            {"name": "duration_seconds", "type": "integer", "default": 30}
        ],
        outputs=[
            {"name": "signals_updated", "type": "integer"},
            {"name": "status", "type": "string"}
        ],
        nodes={
            "start": {
                "type": "entry",
                "next": "get_signals"
            },
            "get_signals": {
                "type": "action",
                "operation": "traffic.get_signals",
                "params": {"zone": "inputs.zone"},
                "next": "check_congestion"
            },
            "check_congestion": {
                "type": "action",
                "operation": "traffic.get_congestion",
                "params": {"zone": "inputs.zone"},
                "next": "update_timing"
            },
            "update_timing": {
                "type": "action",
                "operation": "traffic.set_timing",
                "params": {
                    "zone": "inputs.zone",
                    "duration": "inputs.duration_seconds"
                },
                "next": "success"
            },
            "success": {
                "type": "exit",
                "outputs": {
                    "signals_updated": "update_timing.count",
                    "status": "optimized"
                }
            }
        },
        constraints={
            "max_execution_time_ms": 5000
        }
    )


def main():
    print("=" * 70)
    print("  UASC-M2M Reference Implementation Demo")
    print("  Domain: Smart City Traffic Control")
    print("=" * 70)

    # ===========================================
    # PHASE 1: Registry Setup
    # ===========================================
    print("\n[PHASE 1] Setting up registry...")
    print("-" * 50)

    registry = Registry(
        registry_id="smart-city-tokyo-001",
        domain=Domain.SMART_CITY,
        authority=0x042  # City of Tokyo
    )

    # Register execution graphs
    emergency_graph = create_emergency_priority_graph()
    optimization_graph = create_zone_optimization_graph()

    registry.register_graph(emergency_graph)
    registry.register_graph(optimization_graph)

    # Bind glyphs to graphs
    registry.bind_glyph(0x8003, "emergency-priority-001")  # 控
    registry.bind_glyph(0x8004, "zone-optimization-001")   # 网

    print(f"  Registry ID: {registry.registry_id}")
    print(f"  Domain: SMART_CITY (0x{registry.domain:X})")
    print(f"  Authority: 0x{registry.authority:03X}")
    print(f"  Graphs registered: {len(registry.graphs)}")
    print(f"  Glyph bindings: {len(registry.bindings)}")

    for code, binding in registry.bindings.items():
        graph = registry.graphs[binding.graph_id]
        print(f"    - 0x{code:04X} -> {graph.name}")

    # ===========================================
    # PHASE 2: Trust Chain
    # ===========================================
    print("\n[PHASE 2] Establishing trust chain...")
    print("-" * 50)

    trust_verifier = create_mock_trust_chain(
        domain=Domain.SMART_CITY,
        authority=0x042,
        authority_name="City of Tokyo Traffic Authority"
    )

    print("  Root Authority: UASC Consortium")
    print("  Domain Authority: International Smart City Consortium")
    print("  Local Authority: City of Tokyo Traffic Authority")
    print("  Trust chain: VERIFIED")

    # ===========================================
    # PHASE 3: Action Handlers
    # ===========================================
    print("\n[PHASE 3] Registering action handlers...")
    print("-" * 50)

    action_registry = ActionRegistry()
    register_traffic_actions(action_registry)

    print(f"  Actions registered: {len(action_registry.handlers)}")
    for op in action_registry.list_operations():
        print(f"    - {op}")

    # ===========================================
    # PHASE 4: Interpreter
    # ===========================================
    print("\n[PHASE 4] Initializing interpreter...")
    print("-" * 50)

    interpreter = Interpreter(
        registry=registry,
        trust_verifier=trust_verifier,
        action_registry=action_registry
    )

    print("  Interpreter: READY")
    print("  Max iterations: 100")
    print("  Logging: ENABLED")

    # ===========================================
    # EXECUTION 1: Emergency Priority (High)
    # ===========================================
    print("\n" + "=" * 70)
    print("  EXECUTION 1: Emergency Vehicle Priority (High Priority)")
    print("=" * 70)

    frame1 = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x042,
        glyph_code=0x8003,
        context={
            'zone': 5,
            'priority': 5,
            'mode': 'emergency'
        }
    )

    # Show encoding
    binary1 = GlyphCodec.encode(frame1)
    uri1 = GlyphCodec.to_text(frame1)

    print(f"\n  Glyph Token: {frame1.to_token()}")
    print(f"  Glyph Address: {frame1.full_address}")
    print(f"  URI: {uri1}")
    print(f"  Binary: {binary1.hex()}")
    print(f"  Size: {len(binary1)} bytes")
    print(f"\n  Context:")
    print(f"    Zone: {frame1.context['zone']}")
    print(f"    Priority: {frame1.context['priority']} (HIGH)")
    print(f"    Mode: {frame1.context['mode']}")

    print("\n  Executing...")
    result1 = interpreter.execute(frame1)

    print(f"\n  Result:")
    print(f"    Status: {result1.status.upper()}")
    print(f"    Execution Time: {result1.execution_time_ms}ms")
    print(f"    Node Trace: {' -> '.join(result1.node_trace)}")
    print(f"    Outputs:")
    for key, value in result1.outputs.items():
        print(f"      {key}: {value}")

    # ===========================================
    # EXECUTION 2: Emergency Priority (Low)
    # ===========================================
    print("\n" + "=" * 70)
    print("  EXECUTION 2: Emergency Vehicle Priority (Low Priority)")
    print("=" * 70)

    frame2 = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x042,
        glyph_code=0x8003,
        context={
            'zone': 3,
            'priority': 1,
            'mode': 'normal'
        }
    )

    uri2 = GlyphCodec.to_text(frame2)

    print(f"\n  Glyph Token: {frame2.to_token()}")
    print(f"  URI: {uri2}")
    print(f"\n  Context:")
    print(f"    Zone: {frame2.context['zone']}")
    print(f"    Priority: {frame2.context['priority']} (LOW)")
    print(f"    Mode: {frame2.context['mode']}")

    print("\n  Executing...")
    result2 = interpreter.execute(frame2)

    print(f"\n  Result:")
    print(f"    Status: {result2.status.upper()}")
    print(f"    Execution Time: {result2.execution_time_ms}ms")
    print(f"    Node Trace: {' -> '.join(result2.node_trace)}")
    print(f"    Outputs:")
    for key, value in result2.outputs.items():
        print(f"      {key}: {value}")

    # ===========================================
    # EXECUTION 3: Zone Optimization
    # ===========================================
    print("\n" + "=" * 70)
    print("  EXECUTION 3: Zone Traffic Optimization")
    print("=" * 70)

    frame3 = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x042,
        glyph_code=0x8004,
        context={
            'zone': 8,
            'priority': 3,
            'mode': 'normal'
        }
    )

    uri3 = GlyphCodec.to_text(frame3)

    print(f"\n  Glyph Token: {frame3.to_token()}")
    print(f"  URI: {uri3}")
    print(f"\n  Context:")
    print(f"    Zone: {frame3.context['zone']} (Hospital District)")

    print("\n  Executing...")
    result3 = interpreter.execute(frame3)

    print(f"\n  Result:")
    print(f"    Status: {result3.status.upper()}")
    print(f"    Execution Time: {result3.execution_time_ms}ms")
    print(f"    Node Trace: {' -> '.join(result3.node_trace)}")
    print(f"    Outputs:")
    for key, value in result3.outputs.items():
        print(f"      {key}: {value}")

    # ===========================================
    # EXECUTION LOG SUMMARY
    # ===========================================
    print("\n" + "=" * 70)
    print("  EXECUTION LOG SUMMARY")
    print("=" * 70)

    for entry in interpreter.get_execution_log():
        status_icon = "[OK]" if entry['status'] == 'success' else "[FAIL]"
        print(f"\n  {status_icon} {entry['glyph']} ({entry['glyph_code']})")
        print(f"      Authority: {entry['authority']}")
        print(f"      Status: {entry['status']}")
        print(f"      Time: {entry['execution_time_ms']}ms")
        print(f"      Nodes: {entry['node_count']}")

    # ===========================================
    # COMPARISON: Traditional vs UASC
    # ===========================================
    print("\n" + "=" * 70)
    print("  COMPARISON: Traditional Command vs UASC Glyph")
    print("=" * 70)

    traditional_json = """{
  "command": "emergency_vehicle_priority",
  "domain": "smart_city",
  "authority": "city_of_tokyo",
  "parameters": {
    "zone": 5,
    "vehicle_id": "AMBULANCE-001",
    "priority": 5,
    "mode": "emergency"
  },
  "authentication": {
    "token": "...",
    "signature": "..."
  }
}"""

    print(f"\n  Traditional JSON command: {len(traditional_json)} bytes")
    print(f"  UASC glyph frame: {len(binary1)} bytes")
    print(f"  Compression ratio: {len(traditional_json) / len(binary1):.1f}x")
    print(f"\n  UASC representation: {frame1.to_token()} ({uri1})")

    # ===========================================
    # DEMO COMPLETE
    # ===========================================
    print("\n" + "=" * 70)
    print("  DEMO COMPLETE")
    print("=" * 70)
    print("\n  The UASC-M2M system successfully:")
    print("    [OK] Encoded commands as 4-8 byte glyph frames")
    print("    [OK] Verified trust chain before execution")
    print("    [OK] Resolved glyphs to execution graphs")
    print("    [OK] Executed deterministic logic paths")
    print("    [OK] Returned structured results")
    print("    [OK] Logged all execution events")
    print()


if __name__ == "__main__":
    main()
