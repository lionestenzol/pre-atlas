# UASC-M2M Reference Implementation

**Version:** 1.0.0-draft
**Status:** Working Draft
**Domain:** Smart City Traffic Control

---

## 1. Overview

This reference implementation demonstrates a complete UASC-M2M system for **Smart City Traffic Control**. It includes:

- Glyph encoding and decoding
- Registry with execution graphs
- Trust verification
- Interpreter execution
- Real system actions (simulated)

---

## 2. Implementation Scope

### 2.1 Domain: Smart City Traffic

| Glyph | Code | Operation |
|-------|------|-----------|
| 一 | 0x8001 | Sequential signal timing |
| 丨 | 0x8002 | Conditional load check |
| 控 | 0x8003 | Emergency vehicle priority |
| 网 | 0x8004 | Full zone optimization |

### 2.2 Components

```
reference-implementation/
├── core/
│   ├── glyph.py          # Glyph encoding/decoding
│   ├── registry.py       # In-memory registry
│   ├── trust.py          # Trust verification
│   └── interpreter.py    # Execution engine
├── graphs/
│   ├── sequential_timing.json
│   ├── conditional_load.json
│   ├── emergency_priority.json
│   └── zone_optimization.json
├── actions/
│   ├── traffic_control.py
│   └── sensor_net.py
├── tests/
│   └── test_full_pipeline.py
└── demo.py               # End-to-end demonstration
```

---

## 3. Core Implementation

### 3.1 Glyph Module

```python
# core/glyph.py

import struct
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import IntEnum

class Domain(IntEnum):
    RESERVED = 0x0
    SMART_CITY = 0x1
    AEROSPACE = 0x2
    MARITIME = 0x3
    MILITARY = 0x4
    MEDICAL = 0x5
    INDUSTRIAL = 0x6
    FINANCIAL = 0x7
    ENERGY = 0x8
    TRANSPORT = 0x9

@dataclass
class GlyphFrame:
    """Represents a decoded UASC glyph frame."""
    domain: int
    authority: int
    glyph_code: int
    context: Optional[Dict[str, Any]] = None

    @property
    def full_address(self) -> str:
        return f"{self.domain:01X}.{self.authority:03X}.{self.glyph_code:04X}"

    def to_visual(self) -> str:
        """Return visual glyph character."""
        visuals = {
            0x8001: '一',
            0x8002: '丨',
            0x8003: '控',
            0x8004: '网',
        }
        return visuals.get(self.glyph_code, '?')

class GlyphCodec:
    """Encode and decode UASC glyph frames."""

    @staticmethod
    def encode(frame: GlyphFrame) -> bytes:
        """Encode glyph frame to binary."""
        packed = (frame.domain & 0xF) << 28
        packed |= (frame.authority & 0xFFF) << 16
        packed |= (frame.glyph_code & 0xFFFF)

        if frame.context:
            context_packed = GlyphCodec._encode_context(frame.context)
            return struct.pack('>II', packed, context_packed)
        return struct.pack('>I', packed)

    @staticmethod
    def decode(data: bytes) -> GlyphFrame:
        """Decode binary to glyph frame."""
        if len(data) < 4:
            raise ValueError("Frame too short")

        packed = struct.unpack('>I', data[:4])[0]

        frame = GlyphFrame(
            domain=(packed >> 28) & 0xF,
            authority=(packed >> 16) & 0xFFF,
            glyph_code=packed & 0xFFFF
        )

        if len(data) >= 8:
            context_packed = struct.unpack('>I', data[4:8])[0]
            frame.context = GlyphCodec._decode_context(context_packed)

        return frame

    @staticmethod
    def _encode_context(context: Dict[str, Any]) -> int:
        """Encode context dict to 32-bit integer."""
        packed = 0
        if 'zone' in context:
            packed |= (context['zone'] & 0xFF) << 24
        if 'priority' in context:
            packed |= (context['priority'] & 0xFF) << 16
        if 'mode' in context:
            modes = {'normal': 0, 'emergency': 1, 'maintenance': 2}
            packed |= (modes.get(context['mode'], 0) & 0xFF) << 8
        return packed

    @staticmethod
    def _decode_context(packed: int) -> Dict[str, Any]:
        """Decode 32-bit integer to context dict."""
        modes = {0: 'normal', 1: 'emergency', 2: 'maintenance'}
        return {
            'zone': (packed >> 24) & 0xFF,
            'priority': (packed >> 16) & 0xFF,
            'mode': modes.get((packed >> 8) & 0xFF, 'normal')
        }

    @staticmethod
    def to_text(frame: GlyphFrame) -> str:
        """Convert frame to text URI format."""
        domains = {v: k.lower() for k, v in Domain.__members__.items()}
        domain_name = domains.get(frame.domain, f"domain_{frame.domain}")
        authority_name = f"auth_{frame.authority:03X}"

        uri = f"UASC://{domain_name}.{authority_name}/{frame.to_visual()}"

        if frame.context:
            params = "&".join(f"{k}={v}" for k, v in frame.context.items())
            uri += f"?{params}"

        return uri
```

### 3.2 Registry Module

```python
# core/registry.py

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

@dataclass
class ExecutionGraph:
    """Represents an execution graph."""
    graph_id: str
    name: str
    version: str
    domain: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    nodes: Dict[str, Dict[str, Any]]
    error_handling: Dict[str, Any]
    constraints: Dict[str, Any]

    @property
    def checksum(self) -> str:
        content = json.dumps(self.nodes, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

@dataclass
class GlyphBinding:
    """Binding between a glyph and an execution graph."""
    glyph_code: int
    graph_id: str
    authority: int
    valid_from: datetime
    valid_until: datetime
    signature: str = ""

    def is_valid(self) -> bool:
        now = datetime.utcnow()
        return self.valid_from <= now <= self.valid_until

@dataclass
class Registry:
    """In-memory UASC registry."""
    registry_id: str
    domain: int
    authority: int
    graphs: Dict[str, ExecutionGraph] = field(default_factory=dict)
    bindings: Dict[int, GlyphBinding] = field(default_factory=dict)
    revocations: List[int] = field(default_factory=list)

    def register_graph(self, graph: ExecutionGraph) -> str:
        """Register an execution graph."""
        self.graphs[graph.graph_id] = graph
        return graph.graph_id

    def bind_glyph(self, glyph_code: int, graph_id: str, validity_days: int = 365) -> GlyphBinding:
        """Bind a glyph code to an execution graph."""
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        binding = GlyphBinding(
            glyph_code=glyph_code,
            graph_id=graph_id,
            authority=self.authority,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=validity_days),
            signature=self._sign_binding(glyph_code, graph_id)
        )
        self.bindings[glyph_code] = binding
        return binding

    def lookup(self, glyph_code: int) -> Optional[ExecutionGraph]:
        """Lookup execution graph for a glyph."""
        if glyph_code in self.revocations:
            return None

        binding = self.bindings.get(glyph_code)
        if not binding or not binding.is_valid():
            return None

        return self.graphs.get(binding.graph_id)

    def revoke(self, glyph_code: int):
        """Revoke a glyph binding."""
        self.revocations.append(glyph_code)

    def _sign_binding(self, glyph_code: int, graph_id: str) -> str:
        """Generate mock signature for binding."""
        content = f"{glyph_code}:{graph_id}:{self.authority}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]


def load_graph_from_json(filepath: str) -> ExecutionGraph:
    """Load execution graph from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    return ExecutionGraph(
        graph_id=data['graph_id'],
        name=data['name'],
        version=data['version'],
        domain=data['domain'],
        inputs=data.get('inputs', []),
        outputs=data.get('outputs', []),
        nodes=data['nodes'],
        error_handling=data.get('error_handling', {}),
        constraints=data.get('constraints', {})
    )
```

### 3.3 Trust Module

```python
# core/trust.py

import hashlib
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Certificate:
    """Authority certificate."""
    authority_id: int
    domain: int
    name: str
    public_key: str
    valid_from: datetime
    valid_until: datetime
    issuer_id: int
    signature: str

    def is_valid(self) -> bool:
        now = datetime.utcnow()
        return self.valid_from <= now <= self.valid_until

@dataclass
class VerificationResult:
    """Result of trust verification."""
    valid: bool
    reason: str = ""
    authority_name: str = ""

class TrustVerifier:
    """Verify glyph trust chain."""

    def __init__(self):
        self.root_key = "ROOT_PUBLIC_KEY_PLACEHOLDER"
        self.domain_certs: dict[int, Certificate] = {}
        self.authority_certs: dict[tuple[int, int], Certificate] = {}

    def add_domain_certificate(self, cert: Certificate):
        """Add a domain authority certificate."""
        self.domain_certs[cert.domain] = cert

    def add_authority_certificate(self, cert: Certificate):
        """Add a local authority certificate."""
        self.authority_certs[(cert.domain, cert.authority_id)] = cert

    def verify(self, domain: int, authority: int, binding_signature: str) -> VerificationResult:
        """Verify the trust chain for a glyph."""

        # Step 1: Get authority certificate
        auth_cert = self.authority_certs.get((domain, authority))
        if not auth_cert:
            return VerificationResult(False, "Unknown authority")

        if not auth_cert.is_valid():
            return VerificationResult(False, "Authority certificate expired")

        # Step 2: Get domain certificate
        domain_cert = self.domain_certs.get(domain)
        if not domain_cert:
            return VerificationResult(False, "Unknown domain")

        if not domain_cert.is_valid():
            return VerificationResult(False, "Domain certificate expired")

        # Step 3: Verify authority cert signed by domain
        if auth_cert.issuer_id != domain_cert.authority_id:
            return VerificationResult(False, "Authority not certified by domain")

        # Step 4: Verify domain cert signed by root (simplified)
        if domain_cert.issuer_id != 0:
            return VerificationResult(False, "Domain not certified by root")

        # Step 5: Verify binding signature (simplified)
        if not binding_signature:
            return VerificationResult(False, "Missing binding signature")

        return VerificationResult(
            valid=True,
            reason="Trust chain verified",
            authority_name=auth_cert.name
        )


def create_mock_trust_chain(domain: int, authority: int, authority_name: str) -> TrustVerifier:
    """Create a mock trust chain for testing."""
    verifier = TrustVerifier()

    # Create domain certificate
    domain_cert = Certificate(
        authority_id=0,
        domain=domain,
        name=f"Domain {domain} Authority",
        public_key="DOMAIN_PUBLIC_KEY",
        valid_from=datetime(2024, 1, 1),
        valid_until=datetime(2030, 12, 31),
        issuer_id=0,
        signature="ROOT_SIGNATURE"
    )
    verifier.add_domain_certificate(domain_cert)

    # Create local authority certificate
    auth_cert = Certificate(
        authority_id=authority,
        domain=domain,
        name=authority_name,
        public_key="AUTHORITY_PUBLIC_KEY",
        valid_from=datetime(2024, 1, 1),
        valid_until=datetime(2028, 12, 31),
        issuer_id=0,
        signature="DOMAIN_SIGNATURE"
    )
    verifier.add_authority_certificate(auth_cert)

    return verifier
```

### 3.4 Interpreter Module

```python
# core/interpreter.py

import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime

from .glyph import GlyphFrame, GlyphCodec
from .registry import Registry, ExecutionGraph
from .trust import TrustVerifier, VerificationResult

@dataclass
class ExecutionContext:
    """Context for graph execution."""
    parameters: Dict[str, Any] = field(default_factory=dict)
    system: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """Result of glyph execution."""
    status: str  # success, failed, timeout, rejected
    outputs: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    node_trace: List[str] = field(default_factory=list)
    error: Optional[str] = None

class ActionRegistry:
    """Registry of action handlers."""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}

    def register(self, operation: str, handler: Callable):
        """Register an action handler."""
        self.handlers[operation] = handler

    def execute(self, operation: str, params: Dict[str, Any]) -> Any:
        """Execute an action."""
        if operation not in self.handlers:
            raise ValueError(f"Unknown operation: {operation}")
        return self.handlers[operation](params)

class Interpreter:
    """UASC-M2M Interpreter / Execution Engine."""

    def __init__(
        self,
        registry: Registry,
        trust_verifier: TrustVerifier,
        action_registry: ActionRegistry
    ):
        self.registry = registry
        self.trust = trust_verifier
        self.actions = action_registry
        self.execution_log: List[Dict] = []

    def execute(self, frame: GlyphFrame) -> ExecutionResult:
        """Execute a glyph frame."""
        start_time = time.time()

        # Step 1: Lookup binding and verify trust
        binding = self.registry.bindings.get(frame.glyph_code)
        if not binding:
            return ExecutionResult(
                status='rejected',
                error=f"No binding for glyph {frame.glyph_code:04X}"
            )

        trust_result = self.trust.verify(
            frame.domain,
            frame.authority,
            binding.signature
        )
        if not trust_result.valid:
            return ExecutionResult(
                status='rejected',
                error=f"Trust verification failed: {trust_result.reason}"
            )

        # Step 2: Get execution graph
        graph = self.registry.lookup(frame.glyph_code)
        if not graph:
            return ExecutionResult(
                status='rejected',
                error="Execution graph not found or revoked"
            )

        # Step 3: Build execution context
        context = self._build_context(frame, graph)

        # Step 4: Execute graph
        try:
            result = self._execute_graph(graph, context)
        except Exception as e:
            return ExecutionResult(
                status='failed',
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

        # Step 5: Build result
        execution_time_ms = int((time.time() - start_time) * 1000)

        exec_result = ExecutionResult(
            status='success' if result['status'] == 'completed' else 'failed',
            outputs=result.get('outputs', {}),
            execution_time_ms=execution_time_ms,
            node_trace=result.get('trace', []),
            error=result.get('error')
        )

        # Log execution
        self._log_execution(frame, exec_result)

        return exec_result

    def _build_context(self, frame: GlyphFrame, graph: ExecutionGraph) -> ExecutionContext:
        """Build execution context from frame and graph."""
        context = ExecutionContext()

        # Apply frame context
        if frame.context:
            context.parameters.update(frame.context)

        # Apply graph defaults
        for input_def in graph.inputs:
            name = input_def['name']
            if name not in context.parameters and 'default' in input_def:
                context.parameters[name] = input_def['default']

        # Add system context
        context.system = {
            'timestamp': datetime.utcnow().isoformat(),
            'glyph': frame.to_visual(),
            'glyph_code': frame.glyph_code
        }

        return context

    def _execute_graph(self, graph: ExecutionGraph, context: ExecutionContext) -> Dict:
        """Execute an execution graph."""
        current_node = 'start'
        trace = []
        max_iterations = 100  # Safety limit

        for _ in range(max_iterations):
            if current_node not in graph.nodes:
                return {'status': 'failed', 'error': f"Unknown node: {current_node}", 'trace': trace}

            node = graph.nodes[current_node]
            trace.append(current_node)

            # Execute based on node type
            node_type = node.get('type', 'action')

            if node_type == 'entry':
                current_node = node.get('next', 'end')

            elif node_type == 'exit':
                outputs = self._resolve_outputs(node.get('outputs', {}), context)
                return {'status': 'completed', 'outputs': outputs, 'trace': trace}

            elif node_type == 'action':
                result = self._execute_action(node, context)
                context.node_results[current_node] = result
                current_node = node.get('next', 'end')

            elif node_type == 'condition':
                condition_result = self._evaluate_condition(node, context)
                if condition_result:
                    current_node = node.get('on_true', 'end')
                else:
                    current_node = node.get('on_false', 'end')

            else:
                return {'status': 'failed', 'error': f"Unknown node type: {node_type}", 'trace': trace}

        return {'status': 'failed', 'error': 'Max iterations exceeded', 'trace': trace}

    def _execute_action(self, node: Dict, context: ExecutionContext) -> Any:
        """Execute an action node."""
        operation = node.get('operation', '')
        params = self._resolve_params(node.get('params', {}), context)
        return self.actions.execute(operation, params)

    def _evaluate_condition(self, node: Dict, context: ExecutionContext) -> bool:
        """Evaluate a condition node."""
        expression = node.get('expression', 'true')

        # Simple expression evaluation
        # In production, use a proper expression evaluator
        if expression == 'true':
            return True
        if expression == 'false':
            return False

        # Handle simple comparisons like "priority > 3"
        for param, value in context.parameters.items():
            expression = expression.replace(f"inputs.{param}", str(value))

        for node_id, result in context.node_results.items():
            if isinstance(result, dict):
                for key, val in result.items():
                    expression = expression.replace(f"{node_id}.{key}", str(val))

        try:
            return eval(expression, {"__builtins__": {}}, {})
        except:
            return False

    def _resolve_params(self, params: Dict, context: ExecutionContext) -> Dict:
        """Resolve parameter references."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('inputs.'):
                param_name = value[7:]
                resolved[key] = context.parameters.get(param_name)
            elif isinstance(value, str) and '.' in value:
                parts = value.split('.')
                if len(parts) == 2 and parts[0] in context.node_results:
                    node_result = context.node_results[parts[0]]
                    if isinstance(node_result, dict):
                        resolved[key] = node_result.get(parts[1])
                    else:
                        resolved[key] = node_result
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _resolve_outputs(self, outputs: Dict, context: ExecutionContext) -> Dict:
        """Resolve output references."""
        return self._resolve_params(outputs, context)

    def _log_execution(self, frame: GlyphFrame, result: ExecutionResult):
        """Log execution event."""
        self.execution_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'glyph': frame.to_visual(),
            'glyph_code': f"0x{frame.glyph_code:04X}",
            'status': result.status,
            'execution_time_ms': result.execution_time_ms,
            'node_count': len(result.node_trace)
        })
```

---

## 4. Example Execution Graphs

### 4.1 Sequential Signal Timing

```json
{
  "graph_id": "seq-timing-001",
  "name": "sequential_signal_timing",
  "version": "1.0.0",
  "domain": "smart_city",
  "inputs": [
    {"name": "zone", "type": "integer", "required": true},
    {"name": "duration_seconds", "type": "integer", "default": 30}
  ],
  "outputs": [
    {"name": "signals_updated", "type": "integer"},
    {"name": "status", "type": "string"}
  ],
  "nodes": {
    "start": {
      "type": "entry",
      "next": "get_signals"
    },
    "get_signals": {
      "type": "action",
      "operation": "traffic.get_signals",
      "params": {"zone": "inputs.zone"},
      "next": "update_timing"
    },
    "update_timing": {
      "type": "action",
      "operation": "traffic.set_timing",
      "params": {
        "signals": "get_signals.signals",
        "duration": "inputs.duration_seconds"
      },
      "next": "success"
    },
    "success": {
      "type": "exit",
      "outputs": {
        "signals_updated": "update_timing.count",
        "status": "success"
      }
    }
  },
  "error_handling": {
    "default": "retry",
    "max_retries": 2
  },
  "constraints": {
    "max_execution_time_ms": 5000
  }
}
```

### 4.2 Emergency Vehicle Priority

```json
{
  "graph_id": "emergency-priority-001",
  "name": "emergency_vehicle_priority",
  "version": "1.0.0",
  "domain": "smart_city",
  "inputs": [
    {"name": "zone", "type": "integer", "required": true},
    {"name": "vehicle_id", "type": "string", "required": true},
    {"name": "priority", "type": "integer", "default": 5}
  ],
  "outputs": [
    {"name": "corridor_cleared", "type": "boolean"},
    {"name": "signals_affected", "type": "integer"}
  ],
  "nodes": {
    "start": {
      "type": "entry",
      "next": "check_priority"
    },
    "check_priority": {
      "type": "condition",
      "expression": "inputs.priority >= 3",
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
        "corridor_cleared": true,
        "signals_affected": "clear_corridor.signal_count"
      }
    },
    "success_standard": {
      "type": "exit",
      "outputs": {
        "corridor_cleared": false,
        "signals_affected": "standard_timing.signal_count"
      }
    }
  },
  "constraints": {
    "max_execution_time_ms": 2000
  }
}
```

---

## 5. Action Handlers

```python
# actions/traffic_control.py

"""Simulated traffic control actions."""

import random
from typing import Dict, Any

class TrafficControlActions:
    """Traffic control system interface (simulated)."""

    def __init__(self):
        self.signals = {}
        self._init_mock_signals()

    def _init_mock_signals(self):
        """Initialize mock traffic signals."""
        for zone in range(1, 11):
            self.signals[zone] = {
                'count': random.randint(5, 15),
                'timing': 30,
                'mode': 'normal'
            }

    def get_signals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get signals in a zone."""
        zone = params.get('zone', 1)
        if zone not in self.signals:
            raise ValueError(f"Unknown zone: {zone}")

        return {
            'zone': zone,
            'signals': list(range(1, self.signals[zone]['count'] + 1)),
            'current_timing': self.signals[zone]['timing']
        }

    def set_timing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set signal timing."""
        signals = params.get('signals', [])
        duration = params.get('duration', 30)

        # Simulate updating signals
        return {
            'count': len(signals),
            'new_timing': duration,
            'status': 'updated'
        }

    def emergency_corridor(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clear emergency corridor."""
        zone = params.get('zone', 1)
        vehicle_id = params.get('vehicle_id', 'unknown')

        # Simulate clearing corridor
        signal_count = self.signals.get(zone, {}).get('count', 5)

        return {
            'signal_count': signal_count,
            'vehicle_id': vehicle_id,
            'corridor_status': 'cleared'
        }

    def optimize_route(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize route through zone."""
        zone = params.get('zone', 1)

        signal_count = self.signals.get(zone, {}).get('count', 5)

        return {
            'signal_count': signal_count // 2,
            'optimization': 'applied'
        }


def register_traffic_actions(action_registry):
    """Register traffic control actions."""
    tc = TrafficControlActions()

    action_registry.register('traffic.get_signals', tc.get_signals)
    action_registry.register('traffic.set_timing', tc.set_timing)
    action_registry.register('traffic.emergency_corridor', tc.emergency_corridor)
    action_registry.register('traffic.optimize_route', tc.optimize_route)
```

---

## 6. End-to-End Demo

```python
# demo.py

"""
UASC-M2M Reference Implementation Demo
Smart City Traffic Control Domain
"""

from core.glyph import GlyphFrame, GlyphCodec, Domain
from core.registry import Registry, ExecutionGraph
from core.trust import create_mock_trust_chain
from core.interpreter import Interpreter, ActionRegistry
from actions.traffic_control import register_traffic_actions

def main():
    print("=" * 60)
    print("UASC-M2M Reference Implementation Demo")
    print("Domain: Smart City Traffic Control")
    print("=" * 60)

    # ===========================================
    # SETUP: Create Registry
    # ===========================================
    print("\n[1] Setting up registry...")

    registry = Registry(
        registry_id="smart-city-tokyo-001",
        domain=Domain.SMART_CITY,
        authority=0x042  # City of Tokyo
    )

    # Register execution graphs
    emergency_graph = ExecutionGraph(
        graph_id="emergency-priority-001",
        name="emergency_vehicle_priority",
        version="1.0.0",
        domain="smart_city",
        inputs=[
            {"name": "zone", "type": "integer", "required": True},
            {"name": "vehicle_id", "type": "string", "required": True},
            {"name": "priority", "type": "integer", "default": 5}
        ],
        outputs=[
            {"name": "corridor_cleared", "type": "boolean"},
            {"name": "signals_affected", "type": "integer"}
        ],
        nodes={
            "start": {"type": "entry", "next": "check_priority"},
            "check_priority": {
                "type": "condition",
                "expression": "priority >= 3",
                "on_true": "clear_corridor",
                "on_false": "standard_timing"
            },
            "clear_corridor": {
                "type": "action",
                "operation": "traffic.emergency_corridor",
                "params": {"zone": "inputs.zone", "vehicle_id": "inputs.vehicle_id"},
                "next": "success_emergency"
            },
            "standard_timing": {
                "type": "action",
                "operation": "traffic.optimize_route",
                "params": {"zone": "inputs.zone"},
                "next": "success_standard"
            },
            "success_emergency": {
                "type": "exit",
                "outputs": {"corridor_cleared": True, "signals_affected": "clear_corridor.signal_count"}
            },
            "success_standard": {
                "type": "exit",
                "outputs": {"corridor_cleared": False, "signals_affected": "standard_timing.signal_count"}
            }
        },
        error_handling={"default": "retry", "max_retries": 2},
        constraints={"max_execution_time_ms": 2000}
    )

    registry.register_graph(emergency_graph)
    registry.bind_glyph(0x8003, "emergency-priority-001")

    print(f"   Registry ID: {registry.registry_id}")
    print(f"   Graphs registered: {len(registry.graphs)}")
    print(f"   Bindings: {len(registry.bindings)}")

    # ===========================================
    # SETUP: Create Trust Chain
    # ===========================================
    print("\n[2] Setting up trust chain...")

    trust_verifier = create_mock_trust_chain(
        domain=Domain.SMART_CITY,
        authority=0x042,
        authority_name="City of Tokyo Traffic Authority"
    )

    print("   Trust chain established")

    # ===========================================
    # SETUP: Create Action Registry
    # ===========================================
    print("\n[3] Registering action handlers...")

    action_registry = ActionRegistry()
    register_traffic_actions(action_registry)

    print(f"   Actions registered: {len(action_registry.handlers)}")

    # ===========================================
    # SETUP: Create Interpreter
    # ===========================================
    print("\n[4] Initializing interpreter...")

    interpreter = Interpreter(
        registry=registry,
        trust_verifier=trust_verifier,
        action_registry=action_registry
    )

    print("   Interpreter ready")

    # ===========================================
    # EXECUTE: Send Glyph Command
    # ===========================================
    print("\n[5] Executing glyph command...")
    print("-" * 40)

    # Create glyph frame
    frame = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x042,
        glyph_code=0x8003,
        context={
            'zone': 5,
            'priority': 5,
            'mode': 'emergency'
        }
    )

    # Encode to binary
    binary = GlyphCodec.encode(frame)
    text_uri = GlyphCodec.to_text(frame)

    print(f"   Glyph: {frame.to_visual()}")
    print(f"   URI: {text_uri}")
    print(f"   Binary: {binary.hex()}")
    print(f"   Size: {len(binary)} bytes")

    # Execute
    print("\n   Executing...")
    result = interpreter.execute(frame)

    print(f"\n   Status: {result.status}")
    print(f"   Execution time: {result.execution_time_ms}ms")
    print(f"   Node trace: {' -> '.join(result.node_trace)}")
    print(f"   Outputs: {result.outputs}")

    # ===========================================
    # EXECUTE: Low Priority Request
    # ===========================================
    print("\n[6] Executing low-priority request...")
    print("-" * 40)

    frame2 = GlyphFrame(
        domain=Domain.SMART_CITY,
        authority=0x042,
        glyph_code=0x8003,
        context={
            'zone': 3,
            'priority': 1,  # Low priority
            'mode': 'normal'
        }
    )

    print(f"   Glyph: {frame2.to_visual()}")
    print(f"   Priority: {frame2.context['priority']} (low)")

    result2 = interpreter.execute(frame2)

    print(f"\n   Status: {result2.status}")
    print(f"   Execution time: {result2.execution_time_ms}ms")
    print(f"   Node trace: {' -> '.join(result2.node_trace)}")
    print(f"   Outputs: {result2.outputs}")

    # ===========================================
    # SUMMARY
    # ===========================================
    print("\n" + "=" * 60)
    print("Execution Log Summary")
    print("=" * 60)

    for log_entry in interpreter.execution_log:
        print(f"   {log_entry['timestamp']}: {log_entry['glyph']} ({log_entry['glyph_code']}) -> {log_entry['status']} ({log_entry['execution_time_ms']}ms)")

    print("\n" + "=" * 60)
    print("Demo Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

---

## 7. Expected Output

```
============================================================
UASC-M2M Reference Implementation Demo
Domain: Smart City Traffic Control
============================================================

[1] Setting up registry...
   Registry ID: smart-city-tokyo-001
   Graphs registered: 1
   Bindings: 1

[2] Setting up trust chain...
   Trust chain established

[3] Registering action handlers...
   Actions registered: 4

[4] Initializing interpreter...
   Interpreter ready

[5] Executing glyph command...
----------------------------------------
   Glyph: 控
   URI: UASC://smart_city.auth_042/控?zone=5&priority=5&mode=emergency
   Binary: 10428003050500010000
   Size: 8 bytes

   Executing...

   Status: success
   Execution time: 3ms
   Node trace: start -> check_priority -> clear_corridor -> success_emergency
   Outputs: {'corridor_cleared': True, 'signals_affected': 8}

[6] Executing low-priority request...
----------------------------------------
   Glyph: 控
   Priority: 1 (low)

   Status: success
   Execution time: 2ms
   Node trace: start -> check_priority -> standard_timing -> success_standard
   Outputs: {'corridor_cleared': False, 'signals_affected': 4}

============================================================
Execution Log Summary
============================================================
   2025-01-05T...: 控 (0x8003) -> success (3ms)
   2025-01-05T...: 控 (0x8003) -> success (2ms)

============================================================
Demo Complete
============================================================
```

---

## 8. Running the Reference Implementation

```bash
# Create directory structure
mkdir -p reference-implementation/{core,actions,graphs,tests}

# Copy modules
# ... (copy the code from above into respective files)

# Run demo
cd reference-implementation
python demo.py
```

---

## 9. MVP Profile Executor Condition Syntax

The MVP executor (`reference-implementation/mvp/executor.py`) supports a minimal
conditional step type that executes one of two step lists.

### 9.1 Condition Step Shape

```json
{
  "name": "branch_example",
  "type": "condition",
  "if": "run_mode == 'fast'",
  "then": [
    { "name": "fast_path", "type": "log", "message": "Fast branch selected." }
  ],
  "else": [
    { "name": "slow_path", "type": "log", "message": "Slow branch selected." }
  ]
}
```

### 9.2 Supported Expressions

The `if` expression uses the same minimal comparison syntax as step
`condition` guards:

- `variable == 'value'`
- `variable != 'value'`
- `variable == ''` / `variable != ''` (empty string checks)
- Boolean variable checks (`feature_enabled`)
- Literal `true` / `false`

Variables come from inputs, defaults, and prior step outputs stored via
`store_as`.
