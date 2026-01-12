# MODULE 4 — VECTOR DISCOVERY (Semantic Organizer)

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Use embeddings to detect meaning-level repetition, templates, anomalies, and families of behavior. Proposes dictionary promotions, template suggestions, and routing improvements.

> Observe patterns. Propose structure. Never modify.

---

## Laws

1. **All outputs are PROPOSALS ONLY** — DiscoveryProposal entities only
2. **Never modifies operational entities** — Read-only analysis
3. **Never changes dictionaries directly** — Hand-off to Module 3/5
4. **Requires ≥2 source entities** — No single-point proposals
5. **Fingerprints ensure idempotency** — Same inputs → same proposal ID

---

## Entity Types

### DiscoveryProposal
```typescript
DiscoveryProposalData {
  proposal_type: DiscoveryProposalType;
  source_entity_ids: UUID[];
  proposed_structure: ProposedStructure;
  confidence: number;
  fingerprint: SHA256;
  status: 'NEW' | 'ACCEPTED' | 'REJECTED';
  created_at: Timestamp;
  reviewed_at: Timestamp | null;
  review_notes: string | null;
}

DiscoveryProposalType =
  | 'PATTERN_PROMOTION'
  | 'MOTIF_PROMOTION'
  | 'TEMPLATE_SUGGESTION'
  | 'ROUTING_SUGGESTION'
  | 'ANOMALY';
```

---

## Vector Jobs

| Job Type | Purpose | Trigger |
|----------|---------|---------|
| SEMANTIC_CLUSTER | Find similar texts | New content delta |
| MOTIF_STRUCTURE | Find pattern sequences | Pattern creation |
| ROUTING_PATTERN | Detect mode loops/skips | Mode transition |
| ANOMALY | Find outliers, blocked tasks | Periodic scan |

---

## Semantic Clustering

```typescript
interface SemanticCluster {
  cluster_id: string;
  entity_ids: UUID[];
  centroid: number[];
  example_texts: string[];
  similarity_score: number;
}
```

**Algorithm:** Agglomerative clustering with cosine similarity threshold (0.7)

**Outputs:**
- Same text repeated → PATTERN_PROMOTION
- Similar texts with variation → TEMPLATE_SUGGESTION

---

## Embedding Abstraction

```typescript
interface EmbeddingVector {
  entity_id: UUID;
  text: string;
  vector: number[];      // 8-dimensional for v0
  magnitude: number;
}

function computeEmbedding(entityId: UUID, text: string): EmbeddingVector
function cosineSimilarity(a: EmbeddingVector, b: EmbeddingVector): number
```

**v0 Features (placeholder for real embeddings):**
- Text length
- Question marks
- Exclamation marks
- Request words (please, can you)
- Action words (send, share)
- File words (document, attachment)
- Meeting words (call, schedule)
- Urgency words (urgent, asap)

---

## Routing Analysis

Detects mode progression issues:

| Issue Type | Description | Severity |
|------------|-------------|----------|
| LOOP_DETECTED | Oscillation between modes | HIGH |
| SKIP_DETECTED | Skipped expected mode | MEDIUM |
| STUCK_MODE | No exit from mode | MEDIUM |
| DRIFT | Unintended progressions | LOW |

```typescript
interface RoutingHistory {
  transitions: ModeTransition[];
  mode_counts: Record<Mode, number>;
  transition_counts: Record<string, number>; // "FROM->TO" format
}
```

---

## Anomaly Detection

```typescript
interface DetectedAnomaly {
  entity_id: UUID;
  anomaly_type: 'NOVEL_LANGUAGE' | 'UNUSUAL_FLOW' | 'BLOCKED_LOOP' | 'OUTLIER';
  description: string;
  distance_from_centroid: number;
}
```

**Detection Methods:**
1. Embedding outliers (low similarity to centroid)
2. Blocked task accumulation (≥2 BLOCKED tasks)

---

## Fingerprint Calculation

Ensures idempotent proposal creation:

```typescript
function calculateProposalFingerprint(
  proposalType: DiscoveryProposalType,
  sourceEntityIds: UUID[],
  structureHash: string
): SHA256 {
  // Sort IDs for determinism
  return hashState({
    proposal_type,
    source_ids: sortedIds,
    structure_hash,
  });
}
```

---

## Orchestrator

```typescript
interface VectorDiscoveryContext {
  drafts: Array<{ entity: Entity; state: DraftData }>;
  messages: Array<{ entity: Entity; state: MessageData }>;
  notes: Array<{ entity: Entity; state: NoteData }>;
  tasks: Array<{ entity: Entity; state: TaskData }>;
  patterns: Array<{ entity: Entity; state: PatternData }>;
  motifs: Array<{ entity: Entity; state: MotifData }>;
  routingHistory: RoutingHistory;
  currentMode: Mode;
  existingProposals: Array<{ entity: Entity; state: DiscoveryProposalData }>;
  triggeredByDeltaId: UUID;
}

interface VectorDiscoveryResult {
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
  jobs: VectorJob[];
  clusters: SemanticCluster[];
  anomalies: DetectedAnomaly[];
  routingIssues: RoutingIssue[];
}
```

---

## Trigger Conditions

```typescript
function shouldTriggerDiscovery(delta: Delta): boolean {
  // Template or params changes
  // New entity creation (genesis deltas)
}
```

---

## Files

| File | Purpose |
|------|---------|
| `vector-discovery.ts` | Full implementation (~1000 lines) |

---

## Constants

```typescript
MIN_CLUSTER_SIZE = 2;        // Minimum entities for proposal
MIN_CONFIDENCE = 0.5;        // Minimum confidence threshold
MAX_PROPOSALS_PER_JOB = 10;  // Cap proposals per job
ANOMALY_THRESHOLD = 0.1;     // Bottom 10% are anomalies
LOOP_DETECTION_THRESHOLD = 3; // Same transition 3+ times = loop
```

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `computeEmbedding()` | Generate embedding vector |
| `cosineSimilarity()` | Compare vectors |
| `clusterEmbeddings()` | Group similar texts |
| `runSemanticClusterJob()` | Find text patterns |
| `runMotifStructureJob()` | Find pattern sequences |
| `runRoutingPatternJob()` | Analyze mode transitions |
| `runAnomalyJob()` | Detect outliers |
| `runVectorDiscoveryEngine()` | Orchestrate all jobs |
| `reviewProposal()` | Accept/reject proposal |

---

## Data Flow

```
Content Changes → shouldTriggerDiscovery()
                        ↓
              runVectorDiscoveryEngine()
                        ↓
         ┌──────────────┼──────────────┐
         ↓              ↓              ↓
   Cluster Job    Motif Job    Anomaly Job
         ↓              ↓              ↓
         └──────────────┼──────────────┘
                        ↓
              DiscoveryProposals
                        ↓
              Human Review (Module 5)
```

---

## Next: Module 5 — AI Design Layer

Compile accepted proposals into LUT updates.

Command: **Continue to Module 5 — AI Design Layer.**
