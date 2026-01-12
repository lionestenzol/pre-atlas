# UASC-M2M Registry Specification

**Version:** 1.0.0-draft
**Status:** Working Draft

---

## 1. Overview

The UASC Registry is the authoritative store of execution graphs that glyphs reference. A glyph is meaningless without a registry that maps it to executable logic.

```
GLYPH → REGISTRY LOOKUP → EXECUTION_GRAPH → ACTION
```

---

## 2. Core Concepts

### 2.1 Registry

A **Registry** is a trusted data store containing:
- Execution Graph definitions
- Glyph-to-Graph mappings
- Authority metadata
- Version history

### 2.2 Execution Graph

An **Execution Graph** is a deterministic specification of:
- Sequence of operations
- Conditional branches
- Parameters and constraints
- Error handling paths
- Resource requirements

### 2.3 Glyph Binding

A **Glyph Binding** is the association between:
- A specific glyph (symbolic address)
- An execution graph (the logic)
- Authority signature (who authorized it)
- Validity period (when it's active)

---

## 3. Registry Structure

```
REGISTRY
├── metadata/
│   ├── registry_id          # Unique identifier (UUID)
│   ├── authority             # Issuing authority
│   ├── domain                # Domain scope (smart_city, space, military, etc.)
│   ├── version               # Registry version
│   └── public_key            # Authority's public key for verification
│
├── graphs/
│   ├── {graph_id}/
│   │   ├── definition.json   # The execution graph
│   │   ├── signature         # Authority signature
│   │   ├── version           # Graph version
│   │   ├── created_at        # Timestamp
│   │   └── checksum          # Integrity hash
│   └── ...
│
├── bindings/
│   ├── {glyph_code}/
│   │   ├── graph_id          # Reference to execution graph
│   │   ├── authority_sig     # Binding authorization
│   │   ├── valid_from        # Activation timestamp
│   │   ├── valid_until       # Expiration (optional)
│   │   └── context           # Execution context requirements
│   └── ...
│
└── revocations/
    └── {revocation_id}/
        ├── glyph_code        # Revoked glyph
        ├── reason            # Revocation reason
        ├── revoked_at        # Timestamp
        └── authority_sig     # Revocation authorization
```

---

## 4. Registry Types

### 4.1 Sovereign Registry

- Controlled by a single authority (nation, corporation, organization)
- Full control over glyph definitions
- No external dependencies
- Highest trust level within domain

### 4.2 Federated Registry

- Multiple authorities contribute
- Namespaced glyph bindings
- Cross-authority recognition agreements
- Conflict resolution protocol

### 4.3 Local Registry

- Device or system-local
- Subset of sovereign/federated registry
- Cached for offline operation
- Sync protocol with parent registry

---

## 5. Execution Graph Format

### 5.1 Graph Definition Schema

```json
{
  "graph_id": "uuid-v4",
  "version": "1.0.0",
  "name": "traffic_signal_optimization",
  "domain": "smart_city",
  "deterministic": true,

  "inputs": [
    {
      "name": "zone_id",
      "type": "string",
      "required": true
    },
    {
      "name": "priority_level",
      "type": "integer",
      "default": 1,
      "range": [1, 5]
    }
  ],

  "outputs": [
    {
      "name": "status",
      "type": "enum",
      "values": ["success", "partial", "failed"]
    },
    {
      "name": "affected_signals",
      "type": "integer"
    }
  ],

  "nodes": [
    {
      "id": "start",
      "type": "entry",
      "next": "validate_zone"
    },
    {
      "id": "validate_zone",
      "type": "condition",
      "expression": "zone_exists(inputs.zone_id)",
      "on_true": "fetch_traffic_data",
      "on_false": "error_invalid_zone"
    },
    {
      "id": "fetch_traffic_data",
      "type": "action",
      "operation": "SENSOR_NET.read",
      "params": {
        "zone": "inputs.zone_id",
        "metrics": ["flow_rate", "congestion_index", "queue_length"]
      },
      "next": "analyze_patterns"
    },
    {
      "id": "analyze_patterns",
      "type": "action",
      "operation": "AI.analyze_traffic",
      "params": {
        "data": "fetch_traffic_data.result",
        "model": "congestion_v3"
      },
      "next": "apply_optimization"
    },
    {
      "id": "apply_optimization",
      "type": "action",
      "operation": "TRAFFIC_CONTROL.update_signals",
      "params": {
        "zone": "inputs.zone_id",
        "timing": "analyze_patterns.result.optimal_timing"
      },
      "next": "success"
    },
    {
      "id": "success",
      "type": "exit",
      "status": "success",
      "outputs": {
        "status": "success",
        "affected_signals": "apply_optimization.result.count"
      }
    },
    {
      "id": "error_invalid_zone",
      "type": "exit",
      "status": "failed",
      "outputs": {
        "status": "failed",
        "error": "Invalid zone identifier"
      }
    }
  ],

  "error_handling": {
    "default": "retry_with_backoff",
    "max_retries": 3,
    "fallback": "safe_mode"
  },

  "constraints": {
    "max_execution_time_ms": 5000,
    "required_permissions": ["traffic_control.write", "sensor_net.read"],
    "resource_limits": {
      "memory_mb": 128,
      "cpu_percent": 25
    }
  }
}
```

---

## 6. Versioning

### 6.1 Registry Versioning

- **Major:** Breaking changes to lookup protocol
- **Minor:** New features, backward compatible
- **Patch:** Bug fixes, security updates

### 6.2 Graph Versioning

- **Major:** Breaking changes to execution behavior
- **Minor:** New optional features
- **Patch:** Bug fixes preserving behavior

### 6.3 Binding Versioning

Bindings are immutable. To update:
1. Create new binding with new version
2. Optionally revoke old binding
3. Clients transition based on validity periods

---

## 7. Lookup Protocol

### 7.1 Local Lookup

```
1. Client receives GLYPH
2. Check local cache
3. If found and valid → return EXECUTION_GRAPH
4. If not found or expired → remote lookup
```

### 7.2 Remote Lookup

```
REQUEST:
{
  "glyph": "网",
  "glyph_code": "U+7F51",
  "context": {
    "domain": "smart_city",
    "authority": "city_of_example"
  },
  "client_version": "1.0.0"
}

RESPONSE:
{
  "status": "found",
  "binding": {
    "glyph": "网",
    "graph_id": "uuid-xxx",
    "valid_until": "2026-12-31T23:59:59Z"
  },
  "graph": { ... },
  "signature": "base64-encoded-signature"
}
```

### 7.3 Verification

Before executing, client MUST:
1. Verify authority signature on binding
2. Verify graph checksum
3. Check validity period
4. Confirm required permissions available

---

## 8. Synchronization

### 8.1 Full Sync

- Download complete registry
- Used for initial setup or recovery
- Verify all signatures

### 8.2 Delta Sync

- Request changes since last sync timestamp
- Apply incremental updates
- More efficient for ongoing operation

### 8.3 Offline Mode

- Local registry operates independently
- Queue outbound glyphs if needed
- Reconcile on reconnection

---

## 9. Security Considerations

### 9.1 Registry Integrity

- All graphs signed by authority
- Merkle tree for efficient verification
- Tamper detection on all entries

### 9.2 Transport Security

- TLS 1.3+ for all remote lookups
- Certificate pinning for known authorities
- Mutual authentication for federated registries

### 9.3 Revocation

- Immediate propagation of revocations
- Cached entries must honor revocation
- Grace period for transition

---

## 10. Implementation Requirements

### 10.1 Registry Server

- High availability (replicated)
- Low latency lookup (<10ms local, <100ms remote)
- Audit logging of all access
- Rate limiting per client

### 10.2 Client Requirements

- Local cache with TTL
- Signature verification capability
- Graceful degradation on lookup failure
- Revocation list checking

---

## 11. Example: Smart City Registry

```yaml
registry_id: "sc-example-city-001"
authority: "City of Example Traffic Authority"
domain: "smart_city"
version: "1.0.0"

bindings:
  - glyph: "一"
    graph: "traffic_signal_sequential"
    description: "Execute traffic signals in sequence"

  - glyph: "丨"
    graph: "power_grid_conditional_check"
    description: "Check power grid load conditions"

  - glyph: "网"
    graph: "full_traffic_optimization"
    description: "Complete traffic optimization routine"

  - glyph: "控"
    graph: "emergency_override_protocol"
    description: "Emergency vehicle priority override"
```

---

## 12. Future Considerations

- **Distributed registries** (blockchain-backed for decentralization)
- **Cross-domain translation** (mapping between authority namespaces)
- **Dynamic graph generation** (parameterized templates)
- **Quantum-resistant signatures** (post-quantum cryptography)

