# UASC-M2M Authority Model

**Version:** 1.0.0-draft
**Status:** Working Draft

---

## 1. Overview

The Authority Model defines who can:
- Create and publish glyphs
- Operate registries
- Authorize execution
- Revoke or modify bindings

UASC is a **sovereign-grade** system. Trust is explicit, not assumed.

---

## 2. Core Principles

1. **Explicit Trust** — No implicit authority; all trust is declared
2. **Sovereignty** — Each authority controls its own namespace
3. **Verifiability** — All bindings are cryptographically signed
4. **Revocability** — Any binding can be revoked by its authority
5. **Auditability** — All authority actions are logged

---

## 3. Authority Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                    ROOT AUTHORITY                        │
│         (UASC Governance / Standards Body)               │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    DOMAIN     │ │    DOMAIN     │ │    DOMAIN     │
│   AUTHORITY   │ │   AUTHORITY   │ │   AUTHORITY   │
│ (Smart City)  │ │ (Aerospace)   │ │ (Military)    │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
   ┌────┴────┐       ┌────┴────┐       ┌────┴────┐
   ▼         ▼       ▼         ▼       ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│LOCAL │ │LOCAL │ │LOCAL │ │LOCAL │ │LOCAL │ │LOCAL │
│AUTH  │ │AUTH  │ │AUTH  │ │AUTH  │ │AUTH  │ │AUTH  │
│Tokyo │ │Berlin│ │NASA  │ │ESA   │ │USAF  │ │NATO  │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

---

## 4. Authority Types

### 4.1 Root Authority

**Role:** UASC standards governance

**Responsibilities:**
- Define domain allocation
- Certify domain authorities
- Maintain root trust anchors
- Arbitrate cross-domain disputes

**Powers:**
- Allocate domain codes (0x0-0xF)
- Revoke domain authority certification
- Define universal glyphs (domain 0x0)

### 4.2 Domain Authority

**Role:** Govern a specific operational domain

**Responsibilities:**
- Certify local authorities within domain
- Define domain-wide standard glyphs
- Maintain domain registry
- Enforce domain policies

**Powers:**
- Allocate authority codes (0x000-0xFFF within domain)
- Define standard execution graphs
- Revoke local authority certification

**Examples:**
- International Smart City Consortium (SMART_CITY domain)
- ICAO (AEROSPACE domain)
- NATO (MILITARY domain)

### 4.3 Local Authority

**Role:** Operate within a domain for specific jurisdiction

**Responsibilities:**
- Mint glyphs for local operations
- Operate local registry
- Authorize local execution engines
- Audit local glyph usage

**Powers:**
- Mint glyphs in allocated range (0x8000-0xFFFE)
- Bind glyphs to execution graphs
- Revoke own bindings

**Examples:**
- City of Tokyo (local authority under SMART_CITY)
- NASA (local authority under AEROSPACE)
- US Air Force (local authority under MILITARY)

### 4.4 Execution Authority

**Role:** Permission to execute specific glyphs

**Responsibilities:**
- Verify glyph authenticity before execution
- Log execution events
- Enforce resource constraints
- Report anomalies

**Powers:**
- Execute authorized glyphs
- Reject unauthorized glyphs
- Request glyph updates

**Examples:**
- Traffic control system in Tokyo
- Voyager 3 onboard computer
- Autonomous vehicle fleet controller

---

## 5. Trust Model

### 5.1 Trust Chain

```
Root Authority (signs)
    ↓
Domain Authority Certificate
    ↓
Domain Authority (signs)
    ↓
Local Authority Certificate
    ↓
Local Authority (signs)
    ↓
Glyph Binding
    ↓
Execution Engine (verifies entire chain)
```

### 5.2 Certificate Structure

```json
{
  "certificate_type": "local_authority",
  "subject": {
    "authority_id": "0x042",
    "name": "City of Example Traffic Authority",
    "domain": "SMART_CITY"
  },
  "issuer": {
    "authority_id": "0x000",
    "name": "International Smart City Consortium"
  },
  "validity": {
    "not_before": "2025-01-01T00:00:00Z",
    "not_after": "2030-12-31T23:59:59Z"
  },
  "permissions": {
    "glyph_range": ["0x8000", "0x8FFF"],
    "can_mint": true,
    "can_revoke": true,
    "max_graphs": 1000
  },
  "public_key": "base64-encoded-public-key",
  "signature": "base64-encoded-signature-by-issuer"
}
```

### 5.3 Trust Verification

```python
def verify_glyph_trust(glyph_frame, binding, local_cert, domain_cert, root_cert):
    # 1. Verify root signature on domain cert
    if not verify_signature(domain_cert, root_cert.public_key):
        return False, "Invalid domain certificate"

    # 2. Verify domain signature on local cert
    if not verify_signature(local_cert, domain_cert.public_key):
        return False, "Invalid local authority certificate"

    # 3. Verify local authority signature on binding
    if not verify_signature(binding, local_cert.public_key):
        return False, "Invalid glyph binding"

    # 4. Verify glyph is within authority's allocated range
    if not in_range(glyph_frame.glyph_code, local_cert.permissions.glyph_range):
        return False, "Glyph outside authority's range"

    # 5. Verify certificates are not expired
    if expired(local_cert) or expired(domain_cert):
        return False, "Certificate expired"

    # 6. Check revocation lists
    if revoked(binding) or revoked(local_cert):
        return False, "Binding or certificate revoked"

    return True, "Trust verified"
```

---

## 6. Cross-Domain Trust

### 6.1 Federation Agreements

Authorities in different domains can establish trust:

```json
{
  "agreement_type": "cross_domain_recognition",
  "parties": [
    {"domain": "SMART_CITY", "authority": "city_of_tokyo"},
    {"domain": "TRANSPORT", "authority": "japan_rail"}
  ],
  "scope": {
    "recognized_glyphs": ["控", "网"],
    "permitted_actions": ["read_status", "request_coordination"]
  },
  "validity": {
    "not_before": "2025-01-01T00:00:00Z",
    "not_after": "2027-12-31T23:59:59Z"
  },
  "signatures": ["sig_city_of_tokyo", "sig_japan_rail"]
}
```

### 6.2 Cross-Domain Glyph Resolution

When a glyph references another domain:

```
1. Local authority receives cross-domain glyph
2. Check for federation agreement
3. If agreement exists and valid:
   a. Resolve glyph via federated registry
   b. Verify remote authority's signature
   c. Execute with restricted permissions
4. If no agreement:
   a. Reject glyph
   b. Log attempted cross-domain access
```

---

## 7. Permission Model

### 7.1 Permission Types

| Permission | Description |
|------------|-------------|
| `glyph.mint` | Create new glyph bindings |
| `glyph.revoke` | Revoke existing bindings |
| `glyph.execute` | Execute glyph on system |
| `registry.read` | Read from registry |
| `registry.write` | Write to registry |
| `authority.delegate` | Create sub-authorities |
| `authority.audit` | Access audit logs |

### 7.2 Permission Inheritance

```
Root Authority
├── glyph.mint (domain 0x0 only)
├── authority.delegate (domain level)
└── ALL permissions on own scope

Domain Authority
├── glyph.mint (authority 0x000 in domain)
├── authority.delegate (local level)
├── registry.write (domain registry)
└── Inherited from root for domain scope

Local Authority
├── glyph.mint (allocated range only)
├── glyph.revoke (own bindings only)
├── registry.write (local registry)
└── NO authority.delegate (leaf node)

Execution Engine
├── glyph.execute (authorized glyphs)
├── registry.read (lookup only)
└── NO write permissions
```

### 7.3 Permission Enforcement

```python
class PermissionChecker:
    def check_mint_permission(self, authority, glyph_code):
        # Verify authority has mint permission
        if 'glyph.mint' not in authority.permissions:
            raise PermissionDenied("No mint permission")

        # Verify glyph is in authority's range
        if not self.in_allocated_range(glyph_code, authority):
            raise PermissionDenied("Glyph outside allocated range")

        return True

    def check_execute_permission(self, engine, glyph, binding):
        # Verify engine is authorized for this glyph
        if not self.engine_authorized(engine, binding.authority):
            raise PermissionDenied("Engine not authorized")

        # Verify required system permissions
        for perm in binding.graph.required_permissions:
            if perm not in engine.system_permissions:
                raise PermissionDenied(f"Missing system permission: {perm}")

        return True
```

---

## 8. Revocation

### 8.1 Revocation Types

| Type | Scope | Authority |
|------|-------|-----------|
| Glyph Revocation | Single binding | Binding's local authority |
| Authority Revocation | All bindings by authority | Parent authority |
| Emergency Revocation | Immediate, all systems | Domain or root authority |

### 8.2 Revocation Record

```json
{
  "revocation_id": "uuid",
  "type": "glyph_revocation",
  "target": {
    "glyph": "控",
    "glyph_code": "0x0F02",
    "authority": "city_of_example"
  },
  "reason": "security_vulnerability",
  "revoked_at": "2025-06-15T14:30:00Z",
  "effective_immediately": true,
  "replacement": {
    "glyph": "控",
    "glyph_code": "0x0F03",
    "note": "Patched version"
  },
  "authority_signature": "base64-sig"
}
```

### 8.3 Revocation Propagation

```
1. Authority issues revocation record
2. Signed and published to registry
3. Push notification to all subscribed engines
4. Engines update local cache immediately
5. Grace period for non-critical revocations
6. Hard block for emergency revocations
```

---

## 9. Audit Requirements

### 9.1 Mandatory Audit Events

| Event | Logged By | Retention |
|-------|-----------|-----------|
| Glyph minted | Local authority | Permanent |
| Glyph revoked | Local authority | Permanent |
| Glyph executed | Execution engine | 1 year minimum |
| Authority certified | Parent authority | Permanent |
| Authority revoked | Parent authority | Permanent |
| Trust verification failed | Execution engine | 90 days |
| Cross-domain request | Both authorities | 1 year |

### 9.2 Audit Record Format

```json
{
  "event_id": "uuid",
  "event_type": "glyph_executed",
  "timestamp": "2025-06-15T14:30:00.123Z",
  "actor": {
    "type": "execution_engine",
    "id": "traffic_controller_tokyo_001"
  },
  "subject": {
    "glyph": "網",
    "glyph_code": "0x10420F01",
    "authority": "city_of_tokyo"
  },
  "context": {
    "zone": "shibuya",
    "priority": 2
  },
  "result": {
    "status": "success",
    "execution_time_ms": 47
  },
  "signature": "base64-sig-by-engine"
}
```

---

## 10. Key Management

### 10.1 Key Types

| Key Type | Purpose | Holder |
|----------|---------|--------|
| Root Key | Sign domain certificates | Root authority (HSM) |
| Domain Key | Sign local certificates | Domain authority |
| Authority Key | Sign glyph bindings | Local authority |
| Engine Key | Sign audit records | Execution engine |

### 10.2 Key Rotation

```
1. Generate new key pair
2. Publish new public key with old key signature
3. Grace period: accept both old and new signatures
4. Retire old key after grace period
5. Update all dependent certificates
```

### 10.3 Key Compromise Recovery

```
1. Immediate revocation of compromised key
2. Emergency revocation of all bindings signed by key
3. Re-certification with new key
4. Re-signing of all valid bindings
5. Propagate to all execution engines
6. Forensic audit of potentially malicious bindings
```

---

## 11. Governance

### 11.1 Root Authority Governance

- Multi-stakeholder consortium
- Geographic and sector diversity
- Supermajority (2/3) for domain allocation
- Unanimous for root key operations

### 11.2 Domain Authority Requirements

- Demonstrated expertise in domain
- Operational capacity for registry
- Commitment to UASC standards
- Annual compliance audit

### 11.3 Local Authority Requirements

- Certification by domain authority
- Technical capability assessment
- Security audit (initial and periodic)
- Liability/indemnification agreement

---

## 12. Example: Smart City Authority Chain

```
ROOT AUTHORITY: UASC Consortium
│
├─ Certifies domain...
│
DOMAIN AUTHORITY: International Smart City Consortium
│   Domain: SMART_CITY (0x1)
│   Authority ID: 0x000
│
├─ Certifies local authorities...
│
LOCAL AUTHORITY: City of Tokyo Traffic Bureau
│   Domain: SMART_CITY (0x1)
│   Authority ID: 0x042
│   Glyph Range: 0x8000-0x8FFF
│
├─ Mints glyphs...
│
GLYPH BINDING:
│   Glyph: 控 (0x8001)
│   Graph: emergency_vehicle_priority_v2
│   Signed by: City of Tokyo Traffic Bureau
│
└─ Executed by...

EXECUTION ENGINE: Shibuya Traffic Controller
    Engine ID: traffic_shibuya_001
    Authorized by: City of Tokyo Traffic Bureau
    Permissions: [traffic_control.write, sensor.read]
```

---

## 13. Security Considerations

### 13.1 Threats

| Threat | Mitigation |
|--------|------------|
| Rogue authority | Certificate revocation, audit trails |
| Forged glyph | Signature verification |
| Replay attack | Sequence numbers, timestamps |
| Man-in-the-middle | TLS + certificate pinning |
| Key compromise | HSM storage, rotation, recovery |

### 13.2 Security Requirements

- All authority keys in HSM (Hardware Security Module)
- Minimum 256-bit key strength
- Post-quantum readiness roadmap
- Regular penetration testing
- Bug bounty program

