/**
 * Delta-State Fabric — Module 4: Vector Discovery (Semantic Organizer)
 *
 * Uses embeddings to detect meaning-level repetition, templates, anomalies,
 * and families of behavior. Proposes dictionary promotions, template suggestions,
 * and routing improvements.
 *
 * Laws:
 * - All outputs are PROPOSALS ONLY (DiscoveryProposal entities)
 * - Never modifies operational entities
 * - Never changes dictionaries directly (hand-off to Module 3/5)
 * - Requires ≥2 source entities for any proposal
 * - Fingerprints ensure idempotency
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Mode,
  Entity,
  Delta,
  DiscoveryProposalData,
  DiscoveryProposalType,
  ProposedStructure,
  PatternPromotionStructure,
  MotifPromotionStructure,
  TemplateSuggestionStructure,
  RoutingSuggestionStructure,
  AnomalyStructure,
  DraftData,
  MessageData,
  NoteData,
  TaskData,
  TokenData,
  PatternData,
  MotifData,
  SystemStateData,
} from './types';
import { createEntity, now, hashState, generateUUID } from './delta';

// === CONSTANTS ===

const MIN_CLUSTER_SIZE = 2; // Minimum entities for a proposal
const MIN_CONFIDENCE = 0.5; // Minimum confidence threshold
const MAX_PROPOSALS_PER_JOB = 10;
const ANOMALY_THRESHOLD = 0.1; // Bottom 10% are anomalies
const LOOP_DETECTION_THRESHOLD = 3; // Same mode transition 3+ times = loop

// === VECTOR JOB TYPES ===

export type VectorJobType =
  | 'SEMANTIC_CLUSTER'
  | 'MOTIF_STRUCTURE'
  | 'ROUTING_PATTERN'
  | 'ANOMALY';

export type VectorJobStatus = 'RUNNING' | 'DONE' | 'FAILED' | 'SKIPPED';

export interface VectorJob {
  job_id: UUID;
  job_type: VectorJobType;
  triggered_by_delta_id: UUID;
  started_at: Timestamp;
  completed_at?: Timestamp;
  status: VectorJobStatus;
  proposals_created: number;
  notes?: string;
}

// === EMBEDDING ABSTRACTION ===

/**
 * Embedding vector (abstracted - actual implementation would use a real embedding model)
 * For v0, we use a placeholder that hashes content to simulate embeddings
 */
export interface EmbeddingVector {
  entity_id: UUID;
  text: string;
  vector: number[];
  magnitude: number;
}

/**
 * Compute a placeholder embedding for text.
 * In production, this would call an embedding model.
 * For v0, we use character-based heuristics to simulate semantic grouping.
 */
export async function computeEmbedding(
  entityId: UUID,
  text: string
): Promise<EmbeddingVector> {
  // Placeholder: create a simple 8-dimensional "embedding"
  // based on text characteristics (not real semantics, but deterministic)
  const normalized = text.toLowerCase().trim();

  const vector = [
    normalized.length / 100, // Length feature
    (normalized.match(/\?/g) || []).length / 5, // Question marks
    (normalized.match(/!/g) || []).length / 5, // Exclamation marks
    (normalized.match(/please|can you|could you/gi) || []).length, // Request words
    (normalized.match(/send|share|provide|give/gi) || []).length, // Action words
    (normalized.match(/file|doc|document|attachment/gi) || []).length, // File words
    (normalized.match(/meeting|call|schedule/gi) || []).length, // Meeting words
    (normalized.match(/urgent|asap|priority/gi) || []).length, // Urgency words
  ];

  const magnitude = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0)) || 1;

  return {
    entity_id: entityId,
    text,
    vector,
    magnitude,
  };
}

/**
 * Calculate cosine similarity between two embedding vectors
 */
export function cosineSimilarity(a: EmbeddingVector, b: EmbeddingVector): number {
  if (a.vector.length !== b.vector.length) return 0;

  let dotProduct = 0;
  for (let i = 0; i < a.vector.length; i++) {
    dotProduct += a.vector[i] * b.vector[i];
  }

  return dotProduct / (a.magnitude * b.magnitude) || 0;
}

// === CLUSTERING ===

export interface SemanticCluster {
  cluster_id: string;
  entity_ids: UUID[];
  centroid: number[];
  example_texts: string[];
  similarity_score: number;
}

/**
 * Simple agglomerative clustering based on similarity threshold
 */
export function clusterEmbeddings(
  embeddings: EmbeddingVector[],
  similarityThreshold: number = 0.7
): SemanticCluster[] {
  if (embeddings.length < MIN_CLUSTER_SIZE) return [];

  const clusters: SemanticCluster[] = [];
  const assigned = new Set<UUID>();

  for (let i = 0; i < embeddings.length; i++) {
    if (assigned.has(embeddings[i].entity_id)) continue;

    const clusterMembers: EmbeddingVector[] = [embeddings[i]];
    assigned.add(embeddings[i].entity_id);

    // Find similar embeddings
    for (let j = i + 1; j < embeddings.length; j++) {
      if (assigned.has(embeddings[j].entity_id)) continue;

      const similarity = cosineSimilarity(embeddings[i], embeddings[j]);
      if (similarity >= similarityThreshold) {
        clusterMembers.push(embeddings[j]);
        assigned.add(embeddings[j].entity_id);
      }
    }

    // Only create cluster if minimum size met
    if (clusterMembers.length >= MIN_CLUSTER_SIZE) {
      // Calculate centroid
      const dims = clusterMembers[0].vector.length;
      const centroid = new Array(dims).fill(0);
      for (const member of clusterMembers) {
        for (let d = 0; d < dims; d++) {
          centroid[d] += member.vector[d] / clusterMembers.length;
        }
      }

      // Calculate average similarity within cluster
      let totalSim = 0;
      let count = 0;
      for (let a = 0; a < clusterMembers.length; a++) {
        for (let b = a + 1; b < clusterMembers.length; b++) {
          totalSim += cosineSimilarity(clusterMembers[a], clusterMembers[b]);
          count++;
        }
      }
      const avgSimilarity = count > 0 ? totalSim / count : 1;

      clusters.push({
        cluster_id: `cluster-${clusters.length + 1}`,
        entity_ids: clusterMembers.map((m) => m.entity_id),
        centroid,
        example_texts: clusterMembers.slice(0, 3).map((m) => m.text),
        similarity_score: avgSimilarity,
      });
    }
  }

  return clusters;
}

// === FINGERPRINT CALCULATION ===

export async function calculateProposalFingerprint(
  proposalType: DiscoveryProposalType,
  sourceEntityIds: UUID[],
  structureHash: string
): Promise<SHA256> {
  const sortedIds = [...sourceEntityIds].sort();
  return hashState({
    proposal_type: proposalType,
    source_ids: sortedIds,
    structure_hash: structureHash,
  });
}

// === TEXT EXTRACTION ===

export interface TextSource {
  entity_id: UUID;
  entity_type: string;
  text: string;
}

export function extractTextFromDraft(entity: Entity, state: DraftData): TextSource {
  const renderedParams = Object.entries(state.params)
    .map(([k, v]) => `${k}=${v}`)
    .join(' ');
  return {
    entity_id: entity.entity_id,
    entity_type: 'draft',
    text: `${state.template_id} ${renderedParams}`,
  };
}

export function extractTextFromMessage(entity: Entity, state: MessageData): TextSource {
  const renderedParams = Object.entries(state.params)
    .map(([k, v]) => `${k}=${v}`)
    .join(' ');
  return {
    entity_id: entity.entity_id,
    entity_type: 'message',
    text: `${state.template_id} ${renderedParams}`,
  };
}

export function extractTextFromNote(entity: Entity, state: NoteData): TextSource {
  const renderedParams = Object.entries(state.params)
    .map(([k, v]) => `${k}=${v}`)
    .join(' ');
  return {
    entity_id: entity.entity_id,
    entity_type: 'note',
    text: `${state.template_id} ${renderedParams}`,
  };
}

export function extractTextFromTask(entity: Entity, state: TaskData): TextSource {
  const renderedParams = Object.entries(state.title_params || {})
    .map(([k, v]) => `${k}=${v}`)
    .join(' ');
  return {
    entity_id: entity.entity_id,
    entity_type: 'task',
    text: `${state.title_template} ${renderedParams}`,
  };
}

// === ROUTING HISTORY ===

export interface ModeTransition {
  from_mode: Mode;
  to_mode: Mode;
  timestamp: Timestamp;
}

export interface RoutingHistory {
  transitions: ModeTransition[];
  mode_counts: Record<Mode, number>;
  transition_counts: Record<string, number>; // "FROM->TO" format
}

// === JOB 1: SEMANTIC CLUSTER JOB ===

export interface SemanticClusterJobInput {
  drafts: Array<{ entity: Entity; state: DraftData }>;
  messages: Array<{ entity: Entity; state: MessageData }>;
  notes: Array<{ entity: Entity; state: NoteData }>;
  existingProposalFingerprints: Set<string>;
}

export interface SemanticClusterJobOutput {
  clusters: SemanticCluster[];
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
}

export async function runSemanticClusterJob(
  input: SemanticClusterJobInput
): Promise<SemanticClusterJobOutput> {
  // Extract all text sources
  const textSources: TextSource[] = [
    ...input.drafts.map((d) => extractTextFromDraft(d.entity, d.state)),
    ...input.messages.map((m) => extractTextFromMessage(m.entity, m.state)),
    ...input.notes.map((n) => extractTextFromNote(n.entity, n.state)),
  ];

  if (textSources.length < MIN_CLUSTER_SIZE) {
    return { clusters: [], proposals: [] };
  }

  // Compute embeddings
  const embeddings = await Promise.all(
    textSources.map((ts) => computeEmbedding(ts.entity_id, ts.text))
  );

  // Cluster by similarity
  const clusters = clusterEmbeddings(embeddings, 0.7);

  // Generate proposals from clusters
  const proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> = [];

  for (const cluster of clusters.slice(0, MAX_PROPOSALS_PER_JOB)) {
    // Determine proposal type based on cluster characteristics
    const hasVariation = new Set(cluster.example_texts).size > 1;

    if (hasVariation) {
      // Different wording, similar meaning -> PATTERN_PROMOTION or TEMPLATE_SUGGESTION
      const structureHash = await hashState(cluster.example_texts);
      const fingerprint = await calculateProposalFingerprint(
        'TEMPLATE_SUGGESTION',
        cluster.entity_ids,
        structureHash
      );

      if (input.existingProposalFingerprints.has(fingerprint)) continue;

      // Extract common pattern from examples
      const suggestedPattern = extractCommonPattern(cluster.example_texts);
      const slots = extractSlots(cluster.example_texts);

      const structure: TemplateSuggestionStructure = {
        type: 'TEMPLATE_SUGGESTION',
        suggested_template_id: `DISCOVERED_${cluster.cluster_id.toUpperCase()}`,
        pattern: suggestedPattern,
        slots,
        mode_restriction: null,
      };

      const proposalData: DiscoveryProposalData = {
        proposal_type: 'TEMPLATE_SUGGESTION',
        source_entity_ids: cluster.entity_ids,
        proposed_structure: structure,
        confidence: cluster.similarity_score,
        fingerprint,
        status: 'NEW',
        created_at: now(),
        reviewed_at: null,
        review_notes: null,
      };

      const result = await createEntity('discovery_proposal', proposalData);
      proposals.push(result);
    } else {
      // Exact same wording repeated -> PATTERN_PROMOTION
      const structureHash = await hashState(cluster.example_texts[0]);
      const fingerprint = await calculateProposalFingerprint(
        'PATTERN_PROMOTION',
        cluster.entity_ids,
        structureHash
      );

      if (input.existingProposalFingerprints.has(fingerprint)) continue;

      const tokens = tokenize(cluster.example_texts[0]);

      const structure: PatternPromotionStructure = {
        type: 'PATTERN_PROMOTION',
        token_sequence: tokens,
        suggested_pattern_id: `pattern_${generateUUID().slice(0, 8)}`,
        example_texts: cluster.example_texts,
      };

      const proposalData: DiscoveryProposalData = {
        proposal_type: 'PATTERN_PROMOTION',
        source_entity_ids: cluster.entity_ids,
        proposed_structure: structure,
        confidence: cluster.similarity_score,
        fingerprint,
        status: 'NEW',
        created_at: now(),
        reviewed_at: null,
        review_notes: null,
      };

      const result = await createEntity('discovery_proposal', proposalData);
      proposals.push(result);
    }
  }

  return { clusters, proposals };
}

// === JOB 2: MOTIF STRUCTURE JOB ===

export interface MotifStructureJobInput {
  patterns: Array<{ entity: Entity; state: PatternData }>;
  existingMotifs: Array<{ entity: Entity; state: MotifData }>;
  existingProposalFingerprints: Set<string>;
}

export interface PatternSequence {
  sequence_id: string;
  pattern_ids: string[];
  occurrences: number;
  entity_ids: UUID[];
}

export interface MotifStructureJobOutput {
  sequences: PatternSequence[];
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
}

export async function runMotifStructureJob(
  input: MotifStructureJobInput
): Promise<MotifStructureJobOutput> {
  const proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> = [];

  if (input.patterns.length < MIN_CLUSTER_SIZE) {
    return { sequences: [], proposals: [] };
  }

  // Find repeating sequences of patterns
  const sequences = findPatternSequences(input.patterns);

  // Generate MOTIF_PROMOTION proposals for frequent sequences
  for (const seq of sequences.slice(0, MAX_PROPOSALS_PER_JOB)) {
    if (seq.occurrences < MIN_CLUSTER_SIZE) continue;

    // Check if motif already exists
    const existsAsMotif = input.existingMotifs.some(
      (m) => arraysEqual(m.state.pattern_sequence, seq.pattern_ids)
    );
    if (existsAsMotif) continue;

    const structureHash = await hashState(seq.pattern_ids);
    const fingerprint = await calculateProposalFingerprint(
      'MOTIF_PROMOTION',
      seq.entity_ids,
      structureHash
    );

    if (input.existingProposalFingerprints.has(fingerprint)) continue;

    const structure: MotifPromotionStructure = {
      type: 'MOTIF_PROMOTION',
      pattern_sequence: seq.pattern_ids,
      suggested_motif_id: `motif_${generateUUID().slice(0, 8)}`,
      slots: [], // Would be extracted from pattern analysis
    };

    const proposalData: DiscoveryProposalData = {
      proposal_type: 'MOTIF_PROMOTION',
      source_entity_ids: seq.entity_ids,
      proposed_structure: structure,
      confidence: Math.min(seq.occurrences / 5, 1), // More occurrences = higher confidence
      fingerprint,
      status: 'NEW',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
    };

    const result = await createEntity('discovery_proposal', proposalData);
    proposals.push(result);
  }

  return { sequences, proposals };
}

// === JOB 3: ROUTING PATTERN JOB ===

export interface RoutingPatternJobInput {
  routingHistory: RoutingHistory;
  currentMode: Mode;
  existingProposalFingerprints: Set<string>;
}

export interface RoutingIssue {
  issue_type: 'LOOP_DETECTED' | 'SKIP_DETECTED' | 'STUCK_MODE' | 'DRIFT';
  description: string;
  affected_modes: Mode[];
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface RoutingPatternJobOutput {
  issues: RoutingIssue[];
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
}

export async function runRoutingPatternJob(
  input: RoutingPatternJobInput
): Promise<RoutingPatternJobOutput> {
  const issues: RoutingIssue[] = [];
  const proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> = [];

  // Detect loops (same transition repeated)
  for (const [transition, count] of Object.entries(input.routingHistory.transition_counts)) {
    if (count >= LOOP_DETECTION_THRESHOLD) {
      const [from, to] = transition.split('->') as [Mode, Mode];

      // Check for back-and-forth loops
      const reverseTransition = `${to}->${from}`;
      const reverseCount = input.routingHistory.transition_counts[reverseTransition] || 0;

      if (reverseCount >= LOOP_DETECTION_THRESHOLD - 1) {
        issues.push({
          issue_type: 'LOOP_DETECTED',
          description: `Detected oscillation between ${from} and ${to} (${count}/${reverseCount} times)`,
          affected_modes: [from, to],
          severity: 'HIGH',
        });
      }
    }
  }

  // Detect skipped modes (expected progression not followed)
  const expectedProgression: Mode[] = ['RECOVER', 'CLOSE_LOOPS', 'BUILD', 'COMPOUND', 'SCALE'];
  for (let i = 0; i < expectedProgression.length - 2; i++) {
    const skipTransition = `${expectedProgression[i]}->${expectedProgression[i + 2]}`;
    if (input.routingHistory.transition_counts[skipTransition] > 0) {
      issues.push({
        issue_type: 'SKIP_DETECTED',
        description: `Skipped ${expectedProgression[i + 1]} in progression`,
        affected_modes: [expectedProgression[i], expectedProgression[i + 1], expectedProgression[i + 2]],
        severity: 'MEDIUM',
      });
    }
  }

  // Detect stuck mode (same mode for too long without progress)
  const modeStuckThreshold = 10; // transitions without leaving a mode
  for (const [mode, count] of Object.entries(input.routingHistory.mode_counts) as [Mode, number][]) {
    const transitionsOut = Object.entries(input.routingHistory.transition_counts)
      .filter(([t]) => t.startsWith(`${mode}->`))
      .reduce((sum, [, c]) => sum + c, 0);

    if (count > modeStuckThreshold && transitionsOut < 2) {
      issues.push({
        issue_type: 'STUCK_MODE',
        description: `Stayed in ${mode} mode with minimal progression`,
        affected_modes: [mode],
        severity: 'MEDIUM',
      });
    }
  }

  // Create proposals for significant issues
  for (const issue of issues.filter((i) => i.severity !== 'LOW').slice(0, MAX_PROPOSALS_PER_JOB)) {
    const structureHash = await hashState({
      issue_type: issue.issue_type,
      modes: issue.affected_modes,
    });

    // Use a synthetic entity ID based on the issue for source_entity_ids requirement
    const syntheticIds = issue.affected_modes.map((m) => `routing-${m}-${Date.now()}`);

    const fingerprint = await calculateProposalFingerprint(
      'ROUTING_SUGGESTION',
      syntheticIds,
      structureHash
    );

    if (input.existingProposalFingerprints.has(fingerprint)) continue;

    const structure: RoutingSuggestionStructure = {
      type: 'ROUTING_SUGGESTION',
      issue_type: issue.issue_type,
      description: issue.description,
      affected_modes: issue.affected_modes,
      suggested_fix: generateRoutingSuggestion(issue),
    };

    const proposalData: DiscoveryProposalData = {
      proposal_type: 'ROUTING_SUGGESTION',
      source_entity_ids: syntheticIds,
      proposed_structure: structure,
      confidence: issue.severity === 'HIGH' ? 0.9 : 0.7,
      fingerprint,
      status: 'NEW',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
    };

    const result = await createEntity('discovery_proposal', proposalData);
    proposals.push(result);
  }

  return { issues, proposals };
}

// === JOB 4: ANOMALY JOB ===

export interface AnomalyJobInput {
  allEmbeddings: EmbeddingVector[];
  tasks: Array<{ entity: Entity; state: TaskData }>;
  existingProposalFingerprints: Set<string>;
}

export interface DetectedAnomaly {
  entity_id: UUID;
  anomaly_type: 'NOVEL_LANGUAGE' | 'UNUSUAL_FLOW' | 'BLOCKED_LOOP' | 'OUTLIER';
  description: string;
  distance_from_centroid: number;
}

export interface AnomalyJobOutput {
  anomalies: DetectedAnomaly[];
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
}

export async function runAnomalyJob(
  input: AnomalyJobInput
): Promise<AnomalyJobOutput> {
  const anomalies: DetectedAnomaly[] = [];
  const proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> = [];

  // 1. Detect embedding outliers (novel language)
  if (input.allEmbeddings.length >= 3) {
    // Calculate centroid
    const dims = input.allEmbeddings[0].vector.length;
    const centroid: number[] = new Array(dims).fill(0);
    for (const emb of input.allEmbeddings) {
      for (let d = 0; d < dims; d++) {
        centroid[d] += emb.vector[d] / input.allEmbeddings.length;
      }
    }
    const centroidMag = Math.sqrt(centroid.reduce((s, v) => s + v * v, 0)) || 1;
    const centroidEmb: EmbeddingVector = {
      entity_id: 'centroid',
      text: '',
      vector: centroid,
      magnitude: centroidMag,
    };

    // Find outliers (low similarity to centroid)
    const withDistances = input.allEmbeddings.map((emb) => ({
      emb,
      similarity: cosineSimilarity(emb, centroidEmb),
    }));

    withDistances.sort((a, b) => a.similarity - b.similarity);

    const outlierCount = Math.max(1, Math.floor(withDistances.length * ANOMALY_THRESHOLD));
    const outliers = withDistances.slice(0, outlierCount);

    for (const outlier of outliers) {
      if (outlier.similarity < 0.3) { // Very dissimilar
        anomalies.push({
          entity_id: outlier.emb.entity_id,
          anomaly_type: 'NOVEL_LANGUAGE',
          description: `Text "${outlier.emb.text.slice(0, 50)}..." is semantically distant from typical content`,
          distance_from_centroid: 1 - outlier.similarity,
        });
      }
    }
  }

  // 2. Detect blocked loops (tasks stuck in BLOCKED)
  const blockedTasks = input.tasks.filter((t) => t.state.status === 'BLOCKED');
  if (blockedTasks.length >= MIN_CLUSTER_SIZE) {
    anomalies.push({
      entity_id: blockedTasks[0].entity.entity_id,
      anomaly_type: 'BLOCKED_LOOP',
      description: `${blockedTasks.length} tasks are stuck in BLOCKED status`,
      distance_from_centroid: 0,
    });
  }

  // Group anomalies by type for proposals
  const anomaliesByType = new Map<string, DetectedAnomaly[]>();
  for (const anomaly of anomalies) {
    const existing = anomaliesByType.get(anomaly.anomaly_type) || [];
    existing.push(anomaly);
    anomaliesByType.set(anomaly.anomaly_type, existing);
  }

  // Create proposals for anomaly groups
  for (const [type, typeAnomalies] of anomaliesByType) {
    if (typeAnomalies.length < MIN_CLUSTER_SIZE) continue;

    const entityIds = typeAnomalies.map((a) => a.entity_id);
    const structureHash = await hashState({ type, count: entityIds.length });
    const fingerprint = await calculateProposalFingerprint('ANOMALY', entityIds, structureHash);

    if (input.existingProposalFingerprints.has(fingerprint)) continue;

    const severity = typeAnomalies.length >= 5 ? 'HIGH' : typeAnomalies.length >= 3 ? 'MEDIUM' : 'LOW';

    const structure: AnomalyStructure = {
      type: 'ANOMALY',
      anomaly_type: type as 'NOVEL_LANGUAGE' | 'UNUSUAL_FLOW' | 'BLOCKED_LOOP' | 'OUTLIER',
      description: `Detected ${typeAnomalies.length} ${type.toLowerCase().replace('_', ' ')} anomalies`,
      severity,
    };

    const proposalData: DiscoveryProposalData = {
      proposal_type: 'ANOMALY',
      source_entity_ids: entityIds,
      proposed_structure: structure,
      confidence: Math.min(typeAnomalies.length / 10, 0.95),
      fingerprint,
      status: 'NEW',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
    };

    const result = await createEntity('discovery_proposal', proposalData);
    proposals.push(result);
  }

  return { anomalies, proposals };
}

// === HELPER FUNCTIONS ===

function tokenize(text: string): string[] {
  return text.toLowerCase().split(/\s+/).filter(Boolean);
}

function extractCommonPattern(texts: string[]): string {
  if (texts.length === 0) return '';
  if (texts.length === 1) return texts[0];

  // Simple common prefix/suffix extraction
  const words = texts.map((t) => t.split(/\s+/));
  const minLen = Math.min(...words.map((w) => w.length));

  const pattern: string[] = [];
  for (let i = 0; i < minLen; i++) {
    const wordSet = new Set(words.map((w) => w[i].toLowerCase()));
    if (wordSet.size === 1) {
      pattern.push(words[0][i]);
    } else {
      pattern.push(`{slot_${i}}`);
    }
  }

  return pattern.join(' ') || texts[0];
}

function extractSlots(texts: string[]): string[] {
  const slots: string[] = [];
  const words = texts.map((t) => t.split(/\s+/));
  const minLen = Math.min(...words.map((w) => w.length));

  for (let i = 0; i < minLen; i++) {
    const wordSet = new Set(words.map((w) => w[i].toLowerCase()));
    if (wordSet.size > 1) {
      slots.push(`slot_${i}`);
    }
  }

  return slots;
}

function findPatternSequences(
  patterns: Array<{ entity: Entity; state: PatternData }>
): PatternSequence[] {
  // Sort by creation time
  const sorted = [...patterns].sort(
    (a, b) => a.entity.created_at - b.entity.created_at
  );

  // Find consecutive pairs/triples
  const sequences: Map<string, PatternSequence> = new Map();

  for (let i = 0; i < sorted.length - 1; i++) {
    const pair = [sorted[i].state.pattern_id, sorted[i + 1].state.pattern_id];
    const key = pair.join('|');

    const existing = sequences.get(key);
    if (existing) {
      existing.occurrences++;
      existing.entity_ids.push(sorted[i].entity.entity_id, sorted[i + 1].entity.entity_id);
    } else {
      sequences.set(key, {
        sequence_id: `seq-${sequences.size + 1}`,
        pattern_ids: pair,
        occurrences: 1,
        entity_ids: [sorted[i].entity.entity_id, sorted[i + 1].entity.entity_id],
      });
    }
  }

  return Array.from(sequences.values())
    .filter((s) => s.occurrences >= MIN_CLUSTER_SIZE)
    .sort((a, b) => b.occurrences - a.occurrences);
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((v, i) => v === b[i]);
}

function generateRoutingSuggestion(issue: RoutingIssue): string {
  switch (issue.issue_type) {
    case 'LOOP_DETECTED':
      return `Consider adding a gate between ${issue.affected_modes.join(' and ')} to prevent oscillation`;
    case 'SKIP_DETECTED':
      return `Review signal thresholds for ${issue.affected_modes[1]} mode entry`;
    case 'STUCK_MODE':
      return `Check if ${issue.affected_modes[0]} mode exit conditions are achievable`;
    case 'DRIFT':
      return 'Review overall routing LUT for unintended state progressions';
    default:
      return 'Review routing configuration';
  }
}

// === ORCHESTRATOR ===

export interface VectorDiscoveryContext {
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

export interface VectorDiscoveryResult {
  proposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }>;
  jobs: VectorJob[];
  clusters: SemanticCluster[];
  anomalies: DetectedAnomaly[];
  routingIssues: RoutingIssue[];
}

let jobCounter = 0;

function createVectorJobId(): UUID {
  return `vector-job-${++jobCounter}-${now()}`;
}

export async function runVectorDiscoveryEngine(
  ctx: VectorDiscoveryContext
): Promise<VectorDiscoveryResult> {
  const jobs: VectorJob[] = [];
  const allProposals: Array<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> = [];

  // Get existing proposal fingerprints
  const existingFingerprints = new Set(
    ctx.existingProposals
      .filter((p) => p.state.status !== 'REJECTED')
      .map((p) => p.state.fingerprint)
  );

  // Job 1: Semantic Clustering
  const clusterJob: VectorJob = {
    job_id: createVectorJobId(),
    job_type: 'SEMANTIC_CLUSTER',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
    proposals_created: 0,
  };
  jobs.push(clusterJob);

  const clusterResult = await runSemanticClusterJob({
    drafts: ctx.drafts,
    messages: ctx.messages,
    notes: ctx.notes,
    existingProposalFingerprints: existingFingerprints,
  });

  clusterJob.completed_at = now();
  clusterJob.status = 'DONE';
  clusterJob.proposals_created = clusterResult.proposals.length;
  clusterJob.notes = `Found ${clusterResult.clusters.length} clusters, created ${clusterResult.proposals.length} proposals`;
  allProposals.push(...clusterResult.proposals);

  // Update fingerprints
  for (const p of clusterResult.proposals) {
    existingFingerprints.add(p.state.fingerprint);
  }

  // Job 2: Motif Structure
  const motifJob: VectorJob = {
    job_id: createVectorJobId(),
    job_type: 'MOTIF_STRUCTURE',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
    proposals_created: 0,
  };
  jobs.push(motifJob);

  const motifResult = await runMotifStructureJob({
    patterns: ctx.patterns,
    existingMotifs: ctx.motifs,
    existingProposalFingerprints: existingFingerprints,
  });

  motifJob.completed_at = now();
  motifJob.status = 'DONE';
  motifJob.proposals_created = motifResult.proposals.length;
  motifJob.notes = `Found ${motifResult.sequences.length} sequences, created ${motifResult.proposals.length} proposals`;
  allProposals.push(...motifResult.proposals);

  for (const p of motifResult.proposals) {
    existingFingerprints.add(p.state.fingerprint);
  }

  // Job 3: Routing Pattern
  const routingJob: VectorJob = {
    job_id: createVectorJobId(),
    job_type: 'ROUTING_PATTERN',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
    proposals_created: 0,
  };
  jobs.push(routingJob);

  const routingResult = await runRoutingPatternJob({
    routingHistory: ctx.routingHistory,
    currentMode: ctx.currentMode,
    existingProposalFingerprints: existingFingerprints,
  });

  routingJob.completed_at = now();
  routingJob.status = 'DONE';
  routingJob.proposals_created = routingResult.proposals.length;
  routingJob.notes = `Found ${routingResult.issues.length} issues, created ${routingResult.proposals.length} proposals`;
  allProposals.push(...routingResult.proposals);

  for (const p of routingResult.proposals) {
    existingFingerprints.add(p.state.fingerprint);
  }

  // Job 4: Anomaly Detection
  const anomalyJob: VectorJob = {
    job_id: createVectorJobId(),
    job_type: 'ANOMALY',
    triggered_by_delta_id: ctx.triggeredByDeltaId,
    started_at: now(),
    status: 'RUNNING',
    proposals_created: 0,
  };
  jobs.push(anomalyJob);

  // Compute embeddings for anomaly detection
  const allTextSources: TextSource[] = [
    ...ctx.drafts.map((d) => extractTextFromDraft(d.entity, d.state)),
    ...ctx.messages.map((m) => extractTextFromMessage(m.entity, m.state)),
    ...ctx.notes.map((n) => extractTextFromNote(n.entity, n.state)),
  ];
  const allEmbeddings = await Promise.all(
    allTextSources.map((ts) => computeEmbedding(ts.entity_id, ts.text))
  );

  const anomalyResult = await runAnomalyJob({
    allEmbeddings,
    tasks: ctx.tasks,
    existingProposalFingerprints: existingFingerprints,
  });

  anomalyJob.completed_at = now();
  anomalyJob.status = 'DONE';
  anomalyJob.proposals_created = anomalyResult.proposals.length;
  anomalyJob.notes = `Found ${anomalyResult.anomalies.length} anomalies, created ${anomalyResult.proposals.length} proposals`;
  allProposals.push(...anomalyResult.proposals);

  return {
    proposals: allProposals,
    jobs,
    clusters: clusterResult.clusters,
    anomalies: anomalyResult.anomalies,
    routingIssues: routingResult.issues,
  };
}

// === DELTA-DRIVEN TRIGGER ===

export function shouldTriggerDiscovery(delta: Delta): boolean {
  // Trigger on content changes that might reveal patterns
  for (const patch of delta.patch) {
    if (
      patch.path.includes('template_id') ||
      patch.path.includes('params') ||
      patch.path.includes('title_template') ||
      patch.path.includes('title_params')
    ) {
      return true;
    }
  }

  // Trigger on new entity creation (genesis deltas)
  if (delta.prev_hash === '0'.repeat(64)) {
    return true;
  }

  return false;
}

// === PROPOSAL ACTIONS ===

export async function reviewProposal(
  entity: Entity,
  state: DiscoveryProposalData,
  decision: 'ACCEPTED' | 'REJECTED',
  notes: string | null = null
): Promise<{ entity: Entity; delta: Delta; state: DiscoveryProposalData }> {
  const { createDelta } = await import('./delta');

  const patches = [
    { op: 'replace' as const, path: '/status', value: decision },
    { op: 'replace' as const, path: '/reviewed_at', value: now() },
    { op: 'replace' as const, path: '/review_notes', value: notes },
  ];

  return createDelta(entity, state, patches, 'user');
}
