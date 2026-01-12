# UASC-M2M Interpreter Specification

**Version:** 1.0.0-draft
**Status:** Working Draft

---

## 1. Overview

The UASC Interpreter (Execution Engine) is the runtime component that:
1. Receives glyph frames
2. Resolves glyphs to execution graphs
3. Executes graphs deterministically
4. Reports results and logs events

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UASC INTERPRETER                          │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │  RECEIVER │→ │  RESOLVER │→ │  EXECUTOR │→ │ REPORTER │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
│        ↓              ↓              ↓              ↓       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │   FRAME   │  │  REGISTRY │  │   STATE   │  │  AUDIT   │ │
│  │  DECODER  │  │   CACHE   │  │  MANAGER  │  │   LOG    │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    SYSTEM INTERFACE                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Hardware APIs | Network APIs | Sensor APIs | etc.   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Execution Pipeline

### 3.1 Pipeline Stages

```
GLYPH FRAME RECEIVED
        │
        ▼
┌───────────────────┐
│ 1. FRAME DECODE   │  Parse binary frame into components
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. TRUST VERIFY   │  Verify authority chain and signatures
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. GRAPH RESOLVE  │  Lookup execution graph from registry
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. CONTEXT BUILD  │  Prepare execution context with parameters
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 5. GRAPH EXECUTE  │  Run execution graph nodes
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 6. RESULT REPORT  │  Return status and log execution
└───────────────────┘
```

### 3.2 Pipeline Timing

| Stage | Target Latency | Max Latency |
|-------|----------------|-------------|
| Frame Decode | < 1 ms | 5 ms |
| Trust Verify | < 5 ms | 50 ms |
| Graph Resolve | < 10 ms (cached) | 100 ms (remote) |
| Context Build | < 1 ms | 10 ms |
| Graph Execute | Variable | Defined by graph |
| Result Report | < 5 ms | 50 ms |

---

## 4. Frame Decoder

### 4.1 Input Formats

```python
class FrameDecoder:
    def decode(self, data: bytes) -> GlyphFrame:
        if len(data) == 4:
            return self._decode_compact(data)
        elif len(data) == 8:
            return self._decode_extended(data)
        elif len(data) > 8:
            return self._decode_batch(data)
        else:
            raise InvalidFrameError("Frame too short")

    def _decode_compact(self, data: bytes) -> GlyphFrame:
        frame = struct.unpack('>I', data)[0]
        return GlyphFrame(
            domain=(frame >> 28) & 0xF,
            authority=(frame >> 16) & 0xFFF,
            glyph_code=frame & 0xFFFF,
            context=None
        )

    def _decode_extended(self, data: bytes) -> GlyphFrame:
        frame, context = struct.unpack('>II', data)
        return GlyphFrame(
            domain=(frame >> 28) & 0xF,
            authority=(frame >> 16) & 0xFFF,
            glyph_code=frame & 0xFFFF,
            context=self._parse_context(context)
        )
```

### 4.2 Glyph Frame Structure

```python
@dataclass
class GlyphFrame:
    domain: int           # 4 bits (0-15)
    authority: int        # 12 bits (0-4095)
    glyph_code: int       # 16 bits (0-65535)
    context: Optional[ExecutionContext]
    timestamp: datetime   # Reception time
    sequence: int         # Sequence number for ordering

@dataclass
class ExecutionContext:
    zone: Optional[int]
    priority: int = 1
    mode: str = "normal"
    parameters: Dict[str, Any] = field(default_factory=dict)
```

---

## 5. Trust Verifier

### 5.1 Verification Steps

```python
class TrustVerifier:
    def __init__(self, trust_store: TrustStore):
        self.trust_store = trust_store
        self.revocation_cache = RevocationCache()

    def verify(self, frame: GlyphFrame, binding: GlyphBinding) -> VerificationResult:
        # Step 1: Get authority chain
        chain = self.trust_store.get_authority_chain(
            frame.domain, frame.authority
        )
        if not chain:
            return VerificationResult(
                valid=False,
                reason="Unknown authority"
            )

        # Step 2: Verify each certificate in chain
        for i, cert in enumerate(chain):
            issuer = chain[i + 1] if i + 1 < len(chain) else self.trust_store.root
            if not self._verify_certificate(cert, issuer):
                return VerificationResult(
                    valid=False,
                    reason=f"Invalid certificate at level {i}"
                )

        # Step 3: Verify binding signature
        authority_cert = chain[0]
        if not self._verify_binding(binding, authority_cert):
            return VerificationResult(
                valid=False,
                reason="Invalid binding signature"
            )

        # Step 4: Check revocation status
        if self.revocation_cache.is_revoked(binding.id):
            return VerificationResult(
                valid=False,
                reason="Binding revoked"
            )

        # Step 5: Check validity period
        now = datetime.utcnow()
        if not (binding.valid_from <= now <= binding.valid_until):
            return VerificationResult(
                valid=False,
                reason="Binding not in validity period"
            )

        return VerificationResult(valid=True)
```

### 5.2 Trust Store

```python
class TrustStore:
    def __init__(self, root_certificate: Certificate):
        self.root = root_certificate
        self.domain_certs: Dict[int, Certificate] = {}
        self.authority_certs: Dict[Tuple[int, int], Certificate] = {}

    def get_authority_chain(self, domain: int, authority: int) -> List[Certificate]:
        """Returns chain from local authority up to (not including) root."""
        chain = []

        # Get local authority cert
        local_cert = self.authority_certs.get((domain, authority))
        if local_cert:
            chain.append(local_cert)

        # Get domain authority cert
        domain_cert = self.domain_certs.get(domain)
        if domain_cert:
            chain.append(domain_cert)

        return chain
```

---

## 6. Graph Resolver

### 6.1 Resolution Strategy

```python
class GraphResolver:
    def __init__(self, registry_client: RegistryClient, cache: GraphCache):
        self.registry = registry_client
        self.cache = cache

    def resolve(self, frame: GlyphFrame) -> ExecutionGraph:
        cache_key = (frame.domain, frame.authority, frame.glyph_code)

        # Step 1: Check local cache
        cached = self.cache.get(cache_key)
        if cached and not cached.expired:
            return cached.graph

        # Step 2: Query registry
        binding = self.registry.lookup_binding(
            domain=frame.domain,
            authority=frame.authority,
            glyph_code=frame.glyph_code
        )

        if not binding:
            raise GlyphNotFoundError(f"No binding for glyph {frame.glyph_code}")

        # Step 3: Fetch execution graph
        graph = self.registry.fetch_graph(binding.graph_id)

        # Step 4: Verify graph integrity
        if not self._verify_graph_checksum(graph, binding.graph_checksum):
            raise IntegrityError("Graph checksum mismatch")

        # Step 5: Cache and return
        self.cache.put(cache_key, graph, ttl=binding.cache_ttl)
        return graph
```

### 6.2 Caching Strategy

| Cache Level | TTL | Size | Eviction |
|-------------|-----|------|----------|
| L1 (Hot) | 60s | 100 graphs | LRU |
| L2 (Warm) | 1h | 1000 graphs | LRU |
| L3 (Persistent) | 24h | 10000 graphs | LRU + TTL |

---

## 7. Context Builder

### 7.1 Context Assembly

```python
class ContextBuilder:
    def __init__(self, system_state: SystemState):
        self.system_state = system_state

    def build(self, frame: GlyphFrame, graph: ExecutionGraph) -> ExecutionContext:
        context = ExecutionContext()

        # Step 1: Apply frame context parameters
        if frame.context:
            context.merge(frame.context)

        # Step 2: Apply graph default parameters
        for input_def in graph.inputs:
            if input_def.name not in context.parameters:
                if input_def.default is not None:
                    context.parameters[input_def.name] = input_def.default
                elif input_def.required:
                    raise MissingParameterError(input_def.name)

        # Step 3: Validate parameter types and ranges
        for input_def in graph.inputs:
            value = context.parameters.get(input_def.name)
            if value is not None:
                self._validate_parameter(value, input_def)

        # Step 4: Inject system state
        context.system = {
            'timestamp': datetime.utcnow(),
            'engine_id': self.system_state.engine_id,
            'resource_levels': self.system_state.resources.snapshot()
        }

        # Step 5: Check permission requirements
        for perm in graph.constraints.required_permissions:
            if not self.system_state.has_permission(perm):
                raise PermissionDeniedError(perm)

        return context
```

---

## 8. Graph Executor

### 8.1 Execution Model

The executor processes execution graphs as **deterministic state machines**.

```python
class GraphExecutor:
    def __init__(self, action_registry: ActionRegistry):
        self.actions = action_registry
        self.execution_stack = []
        self.node_results = {}

    def execute(self, graph: ExecutionGraph, context: ExecutionContext) -> ExecutionResult:
        # Initialize execution state
        state = ExecutionState(
            graph=graph,
            context=context,
            current_node='start',
            status='running'
        )

        # Set execution timeout
        deadline = datetime.utcnow() + timedelta(
            milliseconds=graph.constraints.max_execution_time_ms
        )

        # Execute nodes until terminal state
        while state.status == 'running':
            # Check timeout
            if datetime.utcnow() > deadline:
                return self._handle_timeout(state)

            # Get current node
            node = graph.nodes[state.current_node]

            # Execute node
            result = self._execute_node(node, state)

            # Store result
            self.node_results[node.id] = result

            # Determine next node
            next_node = self._determine_next(node, result, state)

            if next_node is None:
                state.status = 'completed'
            else:
                state.current_node = next_node

        return ExecutionResult(
            status=state.status,
            outputs=self._collect_outputs(graph, state),
            execution_time=state.execution_time,
            node_trace=list(self.node_results.keys())
        )
```

### 8.2 Node Types

```python
class NodeExecutor:
    def execute_node(self, node: GraphNode, state: ExecutionState) -> NodeResult:
        match node.type:
            case 'entry':
                return self._execute_entry(node, state)
            case 'exit':
                return self._execute_exit(node, state)
            case 'action':
                return self._execute_action(node, state)
            case 'condition':
                return self._execute_condition(node, state)
            case 'parallel':
                return self._execute_parallel(node, state)
            case 'loop':
                return self._execute_loop(node, state)
            case _:
                raise UnknownNodeTypeError(node.type)

    def _execute_action(self, node: GraphNode, state: ExecutionState) -> NodeResult:
        # Resolve the action handler
        handler = self.actions.get(node.operation)
        if not handler:
            raise UnknownOperationError(node.operation)

        # Resolve parameters (may reference previous results)
        params = self._resolve_params(node.params, state)

        # Execute the action
        try:
            result = handler.execute(params)
            return NodeResult(status='success', value=result)
        except ActionError as e:
            return NodeResult(status='error', error=str(e))

    def _execute_condition(self, node: GraphNode, state: ExecutionState) -> NodeResult:
        # Evaluate the condition expression
        expr_result = self._evaluate_expression(node.expression, state)

        return NodeResult(
            status='success',
            value=bool(expr_result),
            branch='on_true' if expr_result else 'on_false'
        )
```

### 8.3 Action Registry

```python
class ActionRegistry:
    def __init__(self):
        self.handlers: Dict[str, ActionHandler] = {}

    def register(self, operation: str, handler: ActionHandler):
        self.handlers[operation] = handler

    def get(self, operation: str) -> Optional[ActionHandler]:
        return self.handlers.get(operation)

# Example action handlers
class TrafficControlHandler(ActionHandler):
    def execute(self, params: Dict) -> Any:
        zone = params['zone']
        timing = params['timing']
        # Interface with actual traffic control system
        return traffic_system.update_signals(zone, timing)

class SensorNetHandler(ActionHandler):
    def execute(self, params: Dict) -> Any:
        zone = params['zone']
        metrics = params['metrics']
        # Interface with sensor network
        return sensor_network.read(zone, metrics)
```

---

## 9. Determinism Guarantees

### 9.1 Determinism Requirements

For UASC to be reliable, execution must be **deterministic**:

| Requirement | Implementation |
|-------------|----------------|
| Same input → same output | No random operations in graphs |
| No hidden state | All state explicitly in context |
| Ordered execution | Sequential unless explicitly parallel |
| Timeout handling | Deterministic timeout behavior |
| Error handling | Defined error paths in graph |

### 9.2 Non-Determinism Sources (Prohibited)

```python
# PROHIBITED in execution graphs:

# Random values
random.random()  # NOT ALLOWED

# Current time as logic input
if datetime.now().hour > 12:  # NOT ALLOWED (use context.timestamp)

# External state not in context
if global_variable > 0:  # NOT ALLOWED

# Network calls with variable results
response = http.get(url)  # NOT ALLOWED unless idempotent and cached
```

### 9.3 Allowed Non-Determinism

```python
# ALLOWED (results are captured and logged):

# Current timestamp for logging
log.info(f"Executed at {datetime.utcnow()}")

# Execution duration measurement
start = time.monotonic()
result = action()
duration = time.monotonic() - start

# External state via defined interfaces
sensor_data = context.system.sensors.read()  # Defined interface, logged
```

---

## 10. Error Handling

### 10.1 Error Types

| Error Type | Recovery | Example |
|------------|----------|---------|
| `FrameError` | Reject frame | Malformed frame |
| `TrustError` | Reject, log | Invalid signature |
| `ResolutionError` | Retry, fallback | Registry unavailable |
| `ValidationError` | Reject | Missing parameter |
| `ExecutionError` | Graph-defined | Action failed |
| `TimeoutError` | Abort, safe state | Exceeded deadline |
| `SystemError` | Halt, alert | Hardware failure |

### 10.2 Error Recovery

```python
class ErrorHandler:
    def handle(self, error: ExecutionError, state: ExecutionState) -> ErrorRecovery:
        graph = state.graph

        # Check graph-defined error handling
        if graph.error_handling:
            strategy = graph.error_handling.get(type(error).__name__)
            if strategy:
                return self._apply_strategy(strategy, error, state)

        # Default handling
        match error:
            case TimeoutError():
                return ErrorRecovery(action='abort', safe_state=True)
            case ActionError():
                if state.retry_count < graph.error_handling.max_retries:
                    return ErrorRecovery(action='retry', delay_ms=100 * (2 ** state.retry_count))
                return ErrorRecovery(action='fallback', target=graph.error_handling.fallback)
            case _:
                return ErrorRecovery(action='abort', log_level='error')
```

---

## 11. Result Reporter

### 11.1 Execution Result

```python
@dataclass
class ExecutionResult:
    glyph_frame: GlyphFrame
    status: Literal['success', 'partial', 'failed', 'timeout', 'aborted']
    outputs: Dict[str, Any]
    execution_time_ms: int
    node_trace: List[str]
    error: Optional[str] = None

    def to_audit_record(self) -> AuditRecord:
        return AuditRecord(
            event_type='glyph_executed',
            timestamp=datetime.utcnow(),
            glyph=self.glyph_frame,
            result=self.status,
            execution_time_ms=self.execution_time_ms,
            outputs_hash=hash_dict(self.outputs)
        )
```

### 11.2 Result Codes

| Code | Status | Description |
|------|--------|-------------|
| 0x00 | SUCCESS | Execution completed successfully |
| 0x01 | PARTIAL | Some actions completed, some failed |
| 0x10 | FAILED | Execution failed (recoverable) |
| 0x11 | TIMEOUT | Execution exceeded time limit |
| 0x20 | ABORTED | Execution aborted (error) |
| 0x21 | REJECTED | Glyph rejected (trust/permission) |
| 0xFF | UNKNOWN | Unknown error |

---

## 12. Resource Management

### 12.1 Resource Limits

```python
@dataclass
class ResourceLimits:
    max_memory_mb: int = 128
    max_cpu_percent: int = 25
    max_network_bytes: int = 1_000_000
    max_execution_time_ms: int = 5000
    max_concurrent_actions: int = 10

class ResourceManager:
    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        self.current_usage = ResourceUsage()

    def acquire(self, request: ResourceRequest) -> bool:
        if self._would_exceed_limits(request):
            return False
        self.current_usage.add(request)
        return True

    def release(self, request: ResourceRequest):
        self.current_usage.subtract(request)
```

### 12.2 Execution Isolation

```python
class IsolatedExecutor:
    """Execute graphs in isolated environment."""

    def execute_isolated(self, graph: ExecutionGraph, context: ExecutionContext):
        # Create sandboxed environment
        sandbox = Sandbox(
            memory_limit=graph.constraints.resource_limits.memory_mb,
            cpu_limit=graph.constraints.resource_limits.cpu_percent,
            network_policy=self._build_network_policy(graph)
        )

        # Execute in sandbox
        with sandbox:
            result = self.executor.execute(graph, context)

        return result
```

---

## 13. Concurrency

### 13.1 Parallel Execution

```python
class ParallelNodeExecutor:
    def execute_parallel(self, node: GraphNode, state: ExecutionState) -> NodeResult:
        # Get list of parallel branches
        branches = node.branches

        # Execute all branches concurrently
        with ThreadPoolExecutor(max_workers=len(branches)) as executor:
            futures = {
                executor.submit(self._execute_branch, branch, state): branch
                for branch in branches
            }

            results = {}
            for future in as_completed(futures):
                branch = futures[future]
                try:
                    results[branch.id] = future.result()
                except Exception as e:
                    results[branch.id] = NodeResult(status='error', error=str(e))

        # Merge results based on join strategy
        return self._join_results(results, node.join_strategy)
```

### 13.2 Glyph Queue

```python
class GlyphQueue:
    def __init__(self, max_size: int = 1000):
        self.queue = PriorityQueue(maxsize=max_size)

    def enqueue(self, frame: GlyphFrame):
        priority = self._calculate_priority(frame)
        self.queue.put((priority, frame))

    def dequeue(self) -> GlyphFrame:
        _, frame = self.queue.get()
        return frame

    def _calculate_priority(self, frame: GlyphFrame) -> int:
        # Lower number = higher priority
        base_priority = 100

        if frame.context and frame.context.priority:
            base_priority -= frame.context.priority * 20

        # Emergency glyphs get highest priority
        if frame.glyph_code in EMERGENCY_GLYPHS:
            base_priority = 0

        return base_priority
```

---

## 14. Interpreter Configuration

```yaml
# interpreter-config.yaml

engine:
  id: "traffic_controller_tokyo_001"
  domain: "smart_city"
  authority: "city_of_tokyo"

registry:
  primary: "https://registry.tokyo.smartcity.jp"
  fallback: "https://registry-backup.tokyo.smartcity.jp"
  cache_ttl_seconds: 3600

trust:
  root_certificate: "/etc/uasc/root.crt"
  authority_certificates: "/etc/uasc/authorities/"
  revocation_check_interval_seconds: 60

execution:
  max_concurrent_glyphs: 100
  default_timeout_ms: 5000
  retry_policy:
    max_retries: 3
    backoff_multiplier: 2

resources:
  max_memory_mb: 512
  max_cpu_percent: 50
  network_rate_limit_mbps: 10

logging:
  level: "INFO"
  audit_destination: "https://audit.tokyo.smartcity.jp"
  retention_days: 365

actions:
  traffic_control:
    endpoint: "http://localhost:8080/traffic"
  sensor_net:
    endpoint: "http://localhost:8081/sensors"
```

---

## 15. Health and Monitoring

```python
class InterpreterHealth:
    def get_status(self) -> HealthStatus:
        return HealthStatus(
            engine_id=self.config.engine_id,
            status='healthy' if self._all_checks_pass() else 'degraded',
            uptime_seconds=self._get_uptime(),
            glyphs_processed=self.metrics.glyphs_processed,
            glyphs_failed=self.metrics.glyphs_failed,
            avg_execution_time_ms=self.metrics.avg_execution_time,
            registry_connected=self.registry_client.is_connected(),
            cache_hit_rate=self.cache.hit_rate(),
            resource_usage=self.resource_manager.current_usage
        )
```

