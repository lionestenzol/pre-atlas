# MODULE 3 — MATRYOSHKA DICTIONARY (LOSSLESS COMPRESSION CORE)

**Status:** LOCKED
**Version:** 1.0.0

---

## Mission

Convert **repetition into structure**.

Everything stored becomes:

> **Template → Parameters → Pattern → Motif → Delta**

No raw blobs. No duplication. No drift.

---

## Dictionary Tiers

| Tier | Name | Purpose |
|------|------|---------|
| Tier 1 | Token Dictionary | Single words, tiles, atomic units |
| Tier 2 | Pattern Dictionary | Sequences of tokens |
| Tier 3 | Motif Dictionary | Sequences of patterns |

All tiers are:
- Append-only
- Versioned
- Delta-native

---

## Entity Types

```typescript
Token {
  token_id: string;
  value: string;
  frequency: number;
  created_at: Timestamp;
}

Pattern {
  pattern_id: string;
  token_sequence: string[];  // token_ids
  frequency: number;
  created_at: Timestamp;
}

Motif {
  motif_id: string;
  pattern_sequence: string[];  // pattern_ids
  frequency: number;
  created_at: Timestamp;
}
```

---

## Discovery Engine

### Triggers

Runs when:
- New Drafts created
- New Messages created
- New Notes created
- New Templates created

### Flow

1. **Tokenization** — Split text into tokens, add new to dictionary
2. **Pattern Extraction** — Find repeating token sequences (≥2 occurrences)
3. **Motif Extraction** — Find repeating pattern sequences (≥2 occurrences)

---

## Promotion Rules

### Promotion is Permanent

Once promoted, future entities MUST reference Pattern/Motif instead of raw tokens.

### Promotion Thresholds

| Level | Threshold |
|-------|-----------|
| Token → Dictionary | 1 occurrence (always add) |
| Token Sequence → Pattern | ≥2 occurrences, length ≥2 |
| Pattern Sequence → Motif | ≥2 occurrences, length ≥2 |

---

## Rewrite Rule

Existing entities may be rewritten by emitting deltas to replace:
- Raw token sequences → Pattern references
- Raw pattern sequences → Motif references

This shrinks storage permanently.

---

## Storage Form (Final)

No entity stores raw strings.

Everything becomes:

```
[MotifID, ParamA, ParamB]
```

or

```
[PatternID, ParamA]
```

or

```
[TokenID, TokenID, TokenID]
```

Reconstruction = expand Motif → Pattern → Token → String.

---

## Example: Promotion Flow

### Before (raw):

```
Message: "I will resolve this by tomorrow"
```

### After Promotion:

**Token LUT:**
```
T1=I, T2=will, T3=resolve, T4=this, T5=by, T6=tomorrow
```

**Pattern LUT:**
```
P1=[T1, T2, T3, T4, T5]  // "I will resolve this by"
```

**Motif LUT:**
```
M1=[P1, {time}]  // "I will resolve this by {time}"
```

**Delta Rewrite:**
```json
PATCH: [
  { "op": "replace", "path": "/content", "value": { "motif": "M1", "params": { "time": "T6" } } }
]
```

---

## Delta Flows

### New Token

```json
PATCH: [
  { "op": "add", "path": "/token_id", "value": "T7" },
  { "op": "add", "path": "/value", "value": "meeting" },
  { "op": "add", "path": "/frequency", "value": 1 }
]
```

### Frequency Update

```json
PATCH: [
  { "op": "replace", "path": "/frequency", "value": 5 }
]
```

### Pattern Promotion

```json
PATCH: [
  { "op": "add", "path": "/pattern_id", "value": "P2" },
  { "op": "add", "path": "/token_sequence", "value": ["T1", "T2", "T3"] },
  { "op": "add", "path": "/frequency", "value": 2 }
]
```

### Entity Rewrite

```json
PATCH: [
  { "op": "replace", "path": "/template_id", "value": "M1" },
  { "op": "replace", "path": "/params", "value": { "time": "tomorrow" } }
]
```

---

## Compression Metrics

Track:
- `total_tokens` — Size of token dictionary
- `total_patterns` — Size of pattern dictionary
- `total_motifs` — Size of motif dictionary
- `compression_ratio` — Original bytes / Compressed bytes
- `rewrite_count` — Entities rewritten to use patterns/motifs

---

## Why This Matters

- Storage collapses over time
- Delta sync becomes microscopic
- Every message becomes structured
- All text becomes machine-addressable
- Compression compounds with usage
