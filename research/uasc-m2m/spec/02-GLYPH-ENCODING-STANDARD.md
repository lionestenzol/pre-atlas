# UASC-M2M Glyph Encoding Standard

**Version:** 1.0.0-draft
**Status:** Working Draft

---

## 1. Overview

A UASC glyph is a symbolic address that references an execution graph. This specification defines:
- The glyph space (all possible glyphs)
- Encoding format for transmission
- Namespacing and hierarchy
- Minting and registration process

---

## 2. Design Principles

1. **Compact** — Glyphs must be small for bandwidth-constrained channels
2. **Unambiguous** — One glyph = one meaning within a namespace
3. **Human-Inspectable** — Visual representation for debugging/logging
4. **Machine-Efficient** — Fast lookup and comparison
5. **Extensible** — New glyphs can be minted without breaking existing ones

---

## 3. Glyph Anatomy

A fully-qualified UASC glyph consists of:

```
┌─────────────────────────────────────────────────────┐
│                  UASC GLYPH FRAME                   │
├──────────┬──────────┬──────────┬───────────────────┤
│ DOMAIN   │ AUTHORITY│ GLYPH    │ CONTEXT           │
│ (4 bits) │ (12 bits)│ (16 bits)│ (optional 32 bits)│
├──────────┴──────────┴──────────┴───────────────────┤
│ Minimum: 32 bits (4 bytes)                         │
│ Maximum: 64 bits (8 bytes) with context            │
└─────────────────────────────────────────────────────┘
```

---

## 4. Glyph Components

### 4.1 Domain (4 bits)

Defines the operational domain:

| Code | Domain | Description |
|------|--------|-------------|
| 0x0 | RESERVED | System/meta operations |
| 0x1 | SMART_CITY | Urban infrastructure |
| 0x2 | AEROSPACE | Aviation and space |
| 0x3 | MARITIME | Naval and shipping |
| 0x4 | MILITARY | Defense systems |
| 0x5 | MEDICAL | Healthcare systems |
| 0x6 | INDUSTRIAL | Manufacturing/logistics |
| 0x7 | FINANCIAL | Financial systems |
| 0x8 | ENERGY | Power grid and utilities |
| 0x9 | TRANSPORT | Ground transportation |
| 0xA | TELECOM | Communications infrastructure |
| 0xB | AGRICULTURE | Farming and food systems |
| 0xC-0xE | RESERVED | Future domains |
| 0xF | CUSTOM | User-defined domains |

### 4.2 Authority (12 bits)

Identifies the issuing authority within a domain:
- 4,096 possible authorities per domain
- Authorities registered with domain governance
- Authority 0x000 = domain-wide universal glyphs

### 4.3 Glyph Code (16 bits)

The actual glyph identifier:
- 65,536 possible glyphs per authority
- Maps to visual representation
- Unique within authority namespace

### 4.4 Context (32 bits, optional)

Runtime parameters embedded in transmission:
- Zone/region identifiers
- Priority levels
- Timestamp or sequence numbers
- Mode flags

---

## 5. Visual Representation

### 5.1 Primary Glyphs (Stroke-Based)

The core glyph vocabulary uses Chinese-inspired characters composed of primitive strokes:

**Primitive Strokes:**

| Stroke | Name | Unicode | Binary |
|--------|------|---------|--------|
| 一 | Horizontal | U+4E00 | 0b000001 |
| 丨 | Vertical | U+4E28 | 0b000010 |
| 丿 | Diagonal Left | U+4E3F | 0b000100 |
| 乀 | Diagonal Right | U+4E40 | 0b001000 |
| 乙 | Hook | U+4E59 | 0b010000 |
| 丶 | Dot | U+4E36 | 0b100000 |

**Compound Glyphs:**

Composed of 2-8 strokes, each with semantic meaning:

| Glyph | Strokes | Typical Meaning |
|-------|---------|-----------------|
| 网 | 一丨丿乀 | Network/Web operations |
| 问 | 一丨乙丶 | Query/Interrogate |
| 传 | 一丨丿乀丶 | Transmit/Transfer |
| 智 | 一丨丿乀乙丶 | Intelligent processing |
| 控 | 一丨丿乀乙 | Control/Regulate |
| 耀 | 一丨丿乀乙丶一丨 | Integrated system |

### 5.2 Glyph Code Mapping

Each visual glyph maps to a 16-bit code:

```
Stroke composition → Hash → 16-bit code

Example:
网 = 一(0b000001) + 丨(0b000010) + 丿(0b000100) + 乀(0b001000)
  = 0b00001111
  → Extended to 16-bit with position encoding
  → 0x0F01 (example)
```

### 5.3 Reserved Glyph Codes

| Range | Purpose |
|-------|---------|
| 0x0000-0x00FF | System primitives (strokes) |
| 0x0100-0x0FFF | Core vocabulary (universal) |
| 0x1000-0x7FFF | Domain-specific standard |
| 0x8000-0xFFFE | Authority-specific custom |
| 0xFFFF | NULL/No-op |

---

## 6. Wire Format

### 6.1 Compact Format (32-bit)

For bandwidth-constrained transmission:

```
Byte 0:    [DDDD][AAAA]  Domain (4) + Authority high (4)
Byte 1:    [AAAA AAAA]   Authority low (8)
Byte 2-3:  [GGGG GGGG GGGG GGGG]  Glyph code (16)
```

### 6.2 Extended Format (64-bit)

With context parameters:

```
Bytes 0-3: Compact format
Bytes 4-7: Context data
```

### 6.3 Text Format

For logging and human inspection:

```
UASC://{domain}.{authority}/{glyph}[?context]

Examples:
UASC://smart_city.example_city/网
UASC://aerospace.nasa/航?mission=voyager3
UASC://military.usaf/控?priority=critical
```

### 6.4 Binary Encoding

```python
def encode_glyph(domain: int, authority: int, glyph_code: int, context: int = None) -> bytes:
    frame = (domain & 0xF) << 28
    frame |= (authority & 0xFFF) << 16
    frame |= (glyph_code & 0xFFFF)

    if context is not None:
        return struct.pack('>II', frame, context)
    return struct.pack('>I', frame)

def decode_glyph(data: bytes) -> dict:
    frame = struct.unpack('>I', data[:4])[0]
    result = {
        'domain': (frame >> 28) & 0xF,
        'authority': (frame >> 16) & 0xFFF,
        'glyph_code': frame & 0xFFFF
    }
    if len(data) == 8:
        result['context'] = struct.unpack('>I', data[4:8])[0]
    return result
```

---

## 7. Namespacing

### 7.1 Namespace Hierarchy

```
UASC (root)
├── Domain: SMART_CITY (0x1)
│   ├── Authority: city_of_tokyo (0x001)
│   │   ├── Glyph: 网 (0x0F01) → traffic_optimization
│   │   └── Glyph: 控 (0x0F02) → emergency_override
│   └── Authority: city_of_berlin (0x002)
│       └── Glyph: 网 (0x0F01) → different_traffic_impl
│
└── Domain: AEROSPACE (0x2)
    └── Authority: nasa (0x001)
        ├── Glyph: 航 (0x1001) → trajectory_control
        └── Glyph: 探 (0x1002) → planetary_exploration
```

### 7.2 Namespace Resolution

1. **Fully Qualified:** Domain + Authority + Glyph → exact match
2. **Authority Default:** If glyph not in authority, check authority 0x000
3. **Domain Default:** If not in domain, check domain 0x0 (universal)

---

## 8. Glyph Minting

### 8.1 Minting Process

```
1. Authority defines execution graph
2. Authority assigns visual glyph (or auto-generates)
3. Authority computes glyph code from visual
4. Authority signs binding (glyph_code → graph_id)
5. Binding published to registry
6. Glyph becomes valid after propagation
```

### 8.2 Minting Rules

- Authority may only mint within its allocated code range
- Visual glyph must be unique within authority
- Stroke composition must follow valid patterns
- Graph must pass validation before binding

### 8.3 Glyph Generation

For new glyphs, stroke composition follows rules:

```python
def generate_glyph_visual(semantic_tags: list) -> str:
    strokes = []

    if 'sequential' in semantic_tags:
        strokes.append('一')  # Horizontal
    if 'conditional' in semantic_tags:
        strokes.append('丨')  # Vertical
    if 'data_input' in semantic_tags:
        strokes.append('丿')  # Diagonal left
    if 'data_output' in semantic_tags:
        strokes.append('乀')  # Diagonal right
    if 'iterative' in semantic_tags:
        strokes.append('乙')  # Hook
    if 'terminal' in semantic_tags:
        strokes.append('丶')  # Dot

    return compose_character(strokes)
```

---

## 9. Glyph Categories

### 9.1 Primitive Glyphs

Single stroke, basic operations:

| Glyph | Operation |
|-------|-----------|
| 一 | Sequential step |
| 丨 | Condition check |
| 丿 | Data read |
| 乀 | Data write |
| 乙 | Loop/retry |
| 丶 | Complete/confirm |

### 9.2 Compound Glyphs

Multi-stroke, complex operations:

| Glyph | Strokes | Operation |
|-------|---------|-----------|
| 网 | 4 | Network/system operation |
| 控 | 5 | Control routine |
| 智 | 6 | AI/ML processing |
| 耀 | 8 | Integrated multi-system |

### 9.3 Meta Glyphs

System-level operations:

| Glyph | Code | Meaning |
|-------|------|---------|
| ⊘ | 0xFFFF | No-op / NULL |
| ⟳ | 0xFFFE | Retry previous |
| ⊗ | 0xFFFD | Cancel/abort |
| ⟲ | 0xFFFC | Rollback |
| ✓ | 0xFFFB | Acknowledge |

---

## 10. Transmission Considerations

### 10.1 Bandwidth Efficiency

| Format | Size | Use Case |
|--------|------|----------|
| Compact (32-bit) | 4 bytes | Standard operations |
| Extended (64-bit) | 8 bytes | Parameterized operations |
| Batch frame | Variable | Multiple glyphs in sequence |

### 10.2 Batch Transmission

Multiple glyphs in single frame:

```
┌────────┬────────┬────────┬────────┬─────┐
│ COUNT  │ GLYPH1 │ GLYPH2 │ GLYPH3 │ ... │
│ 1 byte │ 4 bytes│ 4 bytes│ 4 bytes│     │
└────────┴────────┴────────┴────────┴─────┘
```

### 10.3 Error Detection

Optional CRC-8 for integrity:

```
┌─────────────────────────┬────────┐
│ GLYPH FRAME (32/64 bit) │ CRC-8  │
└─────────────────────────┴────────┘
```

---

## 11. Comparison with Existing Systems

| System | Symbol Size | Vocabulary | Extensible |
|--------|-------------|------------|------------|
| ASCII command | 1-100+ bytes | Unlimited | Yes |
| CAN bus | 8 bytes | Fixed | No |
| UASC Glyph | 4-8 bytes | 16M+ | Yes |
| Military brevity | Variable | ~500 | Limited |

---

## 12. Examples

### 12.1 Smart City Traffic Command

```
Visual:     控
Domain:     SMART_CITY (0x1)
Authority:  city_example (0x042)
Glyph Code: 0x0F02
Context:    zone=0x0A, priority=0x03

Binary: 0x10420F02 0x0A030000
Text:   UASC://smart_city.city_example/控?zone=10&priority=3
```

### 12.2 Interstellar Probe Command

```
Visual:     航
Domain:     AEROSPACE (0x2)
Authority:  nasa (0x001)
Glyph Code: 0x1001
Context:    mission_phase=0x02

Binary: 0x20011001 0x02000000
Text:   UASC://aerospace.nasa/航?phase=2
```

---

## 13. Future Extensions

- **Glyph composition operators** (combine glyphs at runtime)
- **Parameterized glyph templates** (glyph with variable slots)
- **Glyph aliasing** (multiple visuals for same execution)
- **Animated glyphs** (stroke order encodes sequence)

