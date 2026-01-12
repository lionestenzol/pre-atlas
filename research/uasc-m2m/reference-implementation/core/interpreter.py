"""
UASC-M2M Interpreter Module

The execution engine that processes glyph frames, resolves them
to execution graphs, and deterministically executes the logic.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime

from .glyph import GlyphFrame
from .registry import Registry, ExecutionGraph
from .trust import TrustVerifier


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

    def is_success(self) -> bool:
        return self.status == 'success'


class ActionRegistry:
    """
    Registry of action handlers.

    Maps operation names to callable functions that implement
    the actual system actions (traffic control, sensor reads, etc.)
    """

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

    def has_handler(self, operation: str) -> bool:
        """Check if handler exists for operation."""
        return operation in self.handlers

    def list_operations(self) -> List[str]:
        """List all registered operations."""
        return list(self.handlers.keys())


class Interpreter:
    """
    UASC-M2M Interpreter / Execution Engine.

    The core runtime that:
    1. Receives glyph frames
    2. Verifies trust chain
    3. Resolves execution graphs
    4. Executes graphs deterministically
    5. Returns results and logs events
    """

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
        self.max_iterations = 100  # Safety limit for graph execution

    def execute(self, frame: GlyphFrame) -> ExecutionResult:
        """
        Execute a glyph frame.

        Pipeline:
        1. Lookup binding
        2. Verify trust
        3. Resolve graph
        4. Build context
        5. Execute graph
        6. Return result
        """
        start_time = time.time()

        # Step 1: Lookup binding
        binding = self.registry.get_binding(frame.glyph_code)
        if not binding:
            return self._reject(
                f"No binding for glyph 0x{frame.glyph_code:04X}",
                start_time
            )

        # Step 2: Verify trust
        trust_result = self.trust.verify(
            frame.domain,
            frame.authority,
            binding.signature
        )
        if not trust_result.valid:
            return self._reject(
                f"Trust verification failed: {trust_result.reason}",
                start_time
            )

        # Step 3: Resolve graph
        graph = self.registry.lookup(frame.glyph_code)
        if not graph:
            return self._reject(
                "Execution graph not found or revoked",
                start_time
            )

        # Step 4: Build context
        try:
            context = self._build_context(frame, graph)
        except ValueError as e:
            return self._reject(str(e), start_time)

        # Step 5: Execute graph
        try:
            result = self._execute_graph(graph, context)
        except Exception as e:
            return ExecutionResult(
                status='failed',
                error=str(e),
                execution_time_ms=self._elapsed_ms(start_time)
            )

        # Step 6: Build and return result
        exec_result = ExecutionResult(
            status='success' if result['status'] == 'completed' else 'failed',
            outputs=result.get('outputs', {}),
            execution_time_ms=self._elapsed_ms(start_time),
            node_trace=result.get('trace', []),
            error=result.get('error')
        )

        # Log execution
        self._log_execution(frame, exec_result, trust_result.authority_name)

        return exec_result

    def _reject(self, reason: str, start_time: float) -> ExecutionResult:
        """Create a rejection result."""
        return ExecutionResult(
            status='rejected',
            error=reason,
            execution_time_ms=self._elapsed_ms(start_time)
        )

    def _elapsed_ms(self, start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.time() - start_time) * 1000)

    def _build_context(
        self,
        frame: GlyphFrame,
        graph: ExecutionGraph
    ) -> ExecutionContext:
        """Build execution context from frame and graph."""
        context = ExecutionContext()

        # Apply frame context
        if frame.context:
            context.parameters.update(frame.context)

        # Apply graph defaults and validate required inputs
        for input_def in graph.inputs:
            name = input_def['name']
            if name not in context.parameters:
                if 'default' in input_def:
                    context.parameters[name] = input_def['default']
                elif input_def.get('required', False):
                    raise ValueError(f"Missing required parameter: {name}")

        # Add system context
        context.system = {
            'timestamp': datetime.utcnow().isoformat(),
            'glyph': frame.to_token(),
            'glyph_code': f"0x{frame.glyph_code:04X}",
            'domain': frame.domain,
            'authority': frame.authority
        }

        return context

    def _execute_graph(
        self,
        graph: ExecutionGraph,
        context: ExecutionContext
    ) -> Dict:
        """
        Execute an execution graph.

        Processes nodes sequentially following the graph structure.
        Handles entry, exit, action, and condition node types.
        """
        current_node = 'start'
        trace = []

        for iteration in range(self.max_iterations):
            if current_node not in graph.nodes:
                return {
                    'status': 'failed',
                    'error': f"Unknown node: {current_node}",
                    'trace': trace
                }

            node = graph.nodes[current_node]
            trace.append(current_node)

            node_type = node.get('type', 'action')

            if node_type == 'entry':
                # Entry node - just move to next
                current_node = node.get('next', 'end')

            elif node_type == 'exit':
                # Exit node - resolve outputs and return
                outputs = self._resolve_outputs(node.get('outputs', {}), context)
                return {
                    'status': 'completed',
                    'outputs': outputs,
                    'trace': trace
                }

            elif node_type == 'action':
                # Action node - execute action and store result
                try:
                    result = self._execute_action(node, context)
                    context.node_results[current_node] = result
                except Exception as e:
                    # Check for error handling
                    if 'on_error' in node:
                        current_node = node['on_error']
                        continue
                    raise

                current_node = node.get('next', 'end')

            elif node_type == 'condition':
                # Condition node - evaluate and branch
                condition_result = self._evaluate_condition(node, context)
                if condition_result:
                    current_node = node.get('on_true', 'end')
                else:
                    current_node = node.get('on_false', 'end')

            else:
                return {
                    'status': 'failed',
                    'error': f"Unknown node type: {node_type}",
                    'trace': trace
                }

        # Max iterations exceeded
        return {
            'status': 'failed',
            'error': 'Max iterations exceeded - possible infinite loop',
            'trace': trace
        }

    def _execute_action(self, node: Dict, context: ExecutionContext) -> Any:
        """Execute an action node."""
        operation = node.get('operation', '')
        raw_params = node.get('params', {})
        params = self._resolve_params(raw_params, context)
        return self.actions.execute(operation, params)

    def _evaluate_condition(self, node: Dict, context: ExecutionContext) -> bool:
        """
        Evaluate a condition node.

        Supports simple expressions with parameter references.
        """
        expression = node.get('expression', 'true')

        # Handle literal true/false
        if expression == 'true':
            return True
        if expression == 'false':
            return False

        # Create evaluation context with parameters
        eval_context = dict(context.parameters)

        # Add node results
        for node_id, result in context.node_results.items():
            if isinstance(result, dict):
                for key, val in result.items():
                    eval_context[f"{node_id}_{key}"] = val

        # Replace references in expression
        for param, value in context.parameters.items():
            expression = expression.replace(f"inputs.{param}", repr(value))

        # Safe evaluation
        try:
            # Only allow basic comparisons
            allowed = {"True": True, "False": False}
            allowed.update({k: v for k, v in eval_context.items()
                          if isinstance(v, (int, float, str, bool))})
            return bool(eval(expression, {"__builtins__": {}}, allowed))
        except Exception:
            return False

    def _resolve_params(
        self,
        params: Dict,
        context: ExecutionContext
    ) -> Dict:
        """Resolve parameter references to actual values."""
        resolved = {}

        for key, value in params.items():
            if isinstance(value, str):
                if value.startswith('inputs.'):
                    # Reference to input parameter
                    param_name = value[7:]
                    resolved[key] = context.parameters.get(param_name)
                elif '.' in value:
                    # Reference to node result
                    parts = value.split('.', 1)
                    node_id, result_key = parts
                    node_result = context.node_results.get(node_id, {})
                    if isinstance(node_result, dict):
                        resolved[key] = node_result.get(result_key)
                    else:
                        resolved[key] = node_result
                else:
                    resolved[key] = value
            else:
                resolved[key] = value

        return resolved

    def _resolve_outputs(
        self,
        outputs: Dict,
        context: ExecutionContext
    ) -> Dict:
        """Resolve output references to actual values."""
        return self._resolve_params(outputs, context)

    def _log_execution(
        self,
        frame: GlyphFrame,
        result: ExecutionResult,
        authority_name: str
    ):
        """Log execution event."""
        self.execution_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'glyph': frame.to_token(),
            'glyph_code': f"0x{frame.glyph_code:04X}",
            'authority': authority_name,
            'status': result.status,
            'execution_time_ms': result.execution_time_ms,
            'node_count': len(result.node_trace),
            'error': result.error
        })

    def get_execution_log(self) -> List[Dict]:
        """Get execution log entries."""
        return self.execution_log.copy()

    def clear_execution_log(self):
        """Clear execution log."""
        self.execution_log.clear()
