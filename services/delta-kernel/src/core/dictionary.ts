/**
 * Delta-State Fabric — Module 3: Matryoshka Dictionary
 *
 * Lossless hierarchical compression engine.
 * Converts repetition into structure.
 *
 * Tiers:
 * - Tier 1: Token Dictionary (atomic units)
 * - Tier 2: Pattern Dictionary (token sequences)
 * - Tier 3: Motif Dictionary (pattern sequences)
 *
 * Laws:
 * - Append-only dictionaries
 * - Promotion is permanent
 * - All text becomes machine-addressable
 */

import {
  UUID,
  Timestamp,
  Entity,
  Delta,
  JsonPatch,
  TokenData,
  PatternData,
  MotifData,
  CompressedContent,
  Author,
} from './types';
import { createEntity, createDelta, now, hashState, generateUUID } from './delta';

// === CONSTANTS ===

const MIN_PATTERN_LENGTH = 2;
const MIN_PATTERN_FREQUENCY = 2;
const MIN_MOTIF_LENGTH = 2;
const MIN_MOTIF_FREQUENCY = 2;

// === DICTIONARY STATE ===

export interface DictionaryState {
  tokens: Map<string, { entity: Entity; state: TokenData }>;
  patterns: Map<string, { entity: Entity; state: PatternData }>;
  motifs: Map<string, { entity: Entity; state: MotifData }>;

  // Reverse lookups
  valueToToken: Map<string, string>; // value → token_id
  sequenceToPattern: Map<string, string>; // JSON(token_sequence) → pattern_id
  sequenceToMotif: Map<string, string>; // JSON(pattern_sequence) → motif_id
}

export function createEmptyDictionary(): DictionaryState {
  return {
    tokens: new Map(),
    patterns: new Map(),
    motifs: new Map(),
    valueToToken: new Map(),
    sequenceToPattern: new Map(),
    sequenceToMotif: new Map(),
  };
}

// === TOKEN OPERATIONS ===

let tokenCounter = 0;

function generateTokenId(): string {
  return `T${++tokenCounter}`;
}

export async function getOrCreateToken(
  dict: DictionaryState,
  value: string
): Promise<{
  tokenId: string;
  isNew: boolean;
  delta?: { entity: Entity; delta: Delta; state: TokenData };
}> {
  // Check if token exists
  const existingId = dict.valueToToken.get(value);
  if (existingId) {
    return { tokenId: existingId, isNew: false };
  }

  // Create new token
  const tokenId = generateTokenId();
  const tokenData: TokenData = {
    token_id: tokenId,
    value,
    frequency: 1,
    created_at: now(),
  };

  const result = await createEntity('token', tokenData);

  // Update dictionary state
  dict.tokens.set(tokenId, { entity: result.entity, state: result.state });
  dict.valueToToken.set(value, tokenId);

  return { tokenId, isNew: true, delta: result };
}

export async function incrementTokenFrequency(
  dict: DictionaryState,
  tokenId: string,
  author: Author = 'system'
): Promise<{ entity: Entity; delta: Delta; state: TokenData } | null> {
  const token = dict.tokens.get(tokenId);
  if (!token) return null;

  const patch: JsonPatch[] = [
    { op: 'replace', path: '/frequency', value: token.state.frequency + 1 },
  ];

  const result = await createDelta(token.entity, token.state, patch, author);

  // Update dictionary state
  dict.tokens.set(tokenId, { entity: result.entity, state: result.state });

  return result;
}

// === PATTERN OPERATIONS ===

let patternCounter = 0;

function generatePatternId(): string {
  return `P${++patternCounter}`;
}

function sequenceKey(sequence: string[]): string {
  return JSON.stringify(sequence);
}

export async function getOrCreatePattern(
  dict: DictionaryState,
  tokenSequence: string[]
): Promise<{
  patternId: string;
  isNew: boolean;
  delta?: { entity: Entity; delta: Delta; state: PatternData };
}> {
  const key = sequenceKey(tokenSequence);

  // Check if pattern exists
  const existingId = dict.sequenceToPattern.get(key);
  if (existingId) {
    return { patternId: existingId, isNew: false };
  }

  // Create new pattern
  const patternId = generatePatternId();
  const patternData: PatternData = {
    pattern_id: patternId,
    token_sequence: tokenSequence,
    frequency: 1,
    created_at: now(),
  };

  const result = await createEntity('pattern', patternData);

  // Update dictionary state
  dict.patterns.set(patternId, { entity: result.entity, state: result.state });
  dict.sequenceToPattern.set(key, patternId);

  return { patternId, isNew: true, delta: result };
}

export async function incrementPatternFrequency(
  dict: DictionaryState,
  patternId: string,
  author: Author = 'system'
): Promise<{ entity: Entity; delta: Delta; state: PatternData } | null> {
  const pattern = dict.patterns.get(patternId);
  if (!pattern) return null;

  const patch: JsonPatch[] = [
    { op: 'replace', path: '/frequency', value: pattern.state.frequency + 1 },
  ];

  const result = await createDelta(pattern.entity, pattern.state, patch, author);

  // Update dictionary state
  dict.patterns.set(patternId, { entity: result.entity, state: result.state });

  return result;
}

// === MOTIF OPERATIONS ===

let motifCounter = 0;

function generateMotifId(): string {
  return `M${++motifCounter}`;
}

export async function getOrCreateMotif(
  dict: DictionaryState,
  patternSequence: string[],
  slots: string[] = []
): Promise<{
  motifId: string;
  isNew: boolean;
  delta?: { entity: Entity; delta: Delta; state: MotifData };
}> {
  const key = sequenceKey(patternSequence);

  // Check if motif exists
  const existingId = dict.sequenceToMotif.get(key);
  if (existingId) {
    return { motifId: existingId, isNew: false };
  }

  // Create new motif
  const motifId = generateMotifId();
  const motifData: MotifData = {
    motif_id: motifId,
    pattern_sequence: patternSequence,
    slots,
    frequency: 1,
    created_at: now(),
  };

  const result = await createEntity('motif', motifData);

  // Update dictionary state
  dict.motifs.set(motifId, { entity: result.entity, state: result.state });
  dict.sequenceToMotif.set(key, motifId);

  return { motifId, isNew: true, delta: result };
}

export async function incrementMotifFrequency(
  dict: DictionaryState,
  motifId: string,
  author: Author = 'system'
): Promise<{ entity: Entity; delta: Delta; state: MotifData } | null> {
  const motif = dict.motifs.get(motifId);
  if (!motif) return null;

  const patch: JsonPatch[] = [
    { op: 'replace', path: '/frequency', value: motif.state.frequency + 1 },
  ];

  const result = await createDelta(motif.entity, motif.state, patch, author);

  // Update dictionary state
  dict.motifs.set(motifId, { entity: result.entity, state: result.state });

  return result;
}

// === TOKENIZATION ===

export function tokenize(text: string): string[] {
  // Split on whitespace and punctuation, keep meaningful units
  return text
    .toLowerCase()
    .split(/(\s+|[.,!?;:'"()\[\]{}])/g)
    .filter((t) => t.trim().length > 0);
}

export async function tokenizeText(
  dict: DictionaryState,
  text: string
): Promise<{
  tokenIds: string[];
  newTokenDeltas: Array<{ entity: Entity; delta: Delta; state: TokenData }>;
}> {
  const words = tokenize(text);
  const tokenIds: string[] = [];
  const newTokenDeltas: Array<{ entity: Entity; delta: Delta; state: TokenData }> = [];

  for (const word of words) {
    const result = await getOrCreateToken(dict, word);
    tokenIds.push(result.tokenId);

    if (result.isNew && result.delta) {
      newTokenDeltas.push(result.delta);
    }
  }

  return { tokenIds, newTokenDeltas };
}

// === PATTERN EXTRACTION ===

interface SequenceCount {
  sequence: string[];
  count: number;
  positions: number[][];
}

function findRepeatingSequences(
  tokenIds: string[],
  minLength: number,
  minFrequency: number
): SequenceCount[] {
  const sequences = new Map<string, SequenceCount>();

  // Extract all subsequences of length >= minLength
  for (let len = minLength; len <= Math.min(tokenIds.length, 10); len++) {
    for (let i = 0; i <= tokenIds.length - len; i++) {
      const seq = tokenIds.slice(i, i + len);
      const key = sequenceKey(seq);

      if (!sequences.has(key)) {
        sequences.set(key, { sequence: seq, count: 0, positions: [] });
      }

      const entry = sequences.get(key)!;
      entry.count++;
      entry.positions.push([i, i + len]);
    }
  }

  // Filter by frequency
  return Array.from(sequences.values()).filter((s) => s.count >= minFrequency);
}

export async function extractPatterns(
  dict: DictionaryState,
  tokenIds: string[]
): Promise<{
  promotedPatterns: Array<{ entity: Entity; delta: Delta; state: PatternData }>;
  frequencyUpdates: Array<{ entity: Entity; delta: Delta; state: PatternData }>;
}> {
  const promotedPatterns: Array<{ entity: Entity; delta: Delta; state: PatternData }> = [];
  const frequencyUpdates: Array<{ entity: Entity; delta: Delta; state: PatternData }> = [];

  const repeating = findRepeatingSequences(
    tokenIds,
    MIN_PATTERN_LENGTH,
    MIN_PATTERN_FREQUENCY
  );

  // Sort by length descending (longer patterns first)
  repeating.sort((a, b) => b.sequence.length - a.sequence.length);

  for (const item of repeating) {
    const result = await getOrCreatePattern(dict, item.sequence);

    if (result.isNew && result.delta) {
      promotedPatterns.push(result.delta);
    } else {
      // Increment frequency
      const freqUpdate = await incrementPatternFrequency(dict, result.patternId);
      if (freqUpdate) {
        frequencyUpdates.push(freqUpdate);
      }
    }
  }

  return { promotedPatterns, frequencyUpdates };
}

// === MOTIF EXTRACTION ===

export async function extractMotifs(
  dict: DictionaryState,
  patternIds: string[]
): Promise<{
  promotedMotifs: Array<{ entity: Entity; delta: Delta; state: MotifData }>;
  frequencyUpdates: Array<{ entity: Entity; delta: Delta; state: MotifData }>;
}> {
  const promotedMotifs: Array<{ entity: Entity; delta: Delta; state: MotifData }> = [];
  const frequencyUpdates: Array<{ entity: Entity; delta: Delta; state: MotifData }> = [];

  const repeating = findRepeatingSequences(
    patternIds,
    MIN_MOTIF_LENGTH,
    MIN_MOTIF_FREQUENCY
  );

  // Sort by length descending
  repeating.sort((a, b) => b.sequence.length - a.sequence.length);

  for (const item of repeating) {
    const result = await getOrCreateMotif(dict, item.sequence);

    if (result.isNew && result.delta) {
      promotedMotifs.push(result.delta);
    } else {
      const freqUpdate = await incrementMotifFrequency(dict, result.motifId);
      if (freqUpdate) {
        frequencyUpdates.push(freqUpdate);
      }
    }
  }

  return { promotedMotifs, frequencyUpdates };
}

// === COMPRESSION ===

export function compressTokenSequence(
  dict: DictionaryState,
  tokenIds: string[]
): CompressedContent[] {
  const result: CompressedContent[] = [];
  let i = 0;

  while (i < tokenIds.length) {
    let matched = false;

    // Try to match longest pattern first
    const patterns = Array.from(dict.patterns.values())
      .sort((a, b) => b.state.token_sequence.length - a.state.token_sequence.length);

    for (const pattern of patterns) {
      const seq = pattern.state.token_sequence;
      if (i + seq.length <= tokenIds.length) {
        const slice = tokenIds.slice(i, i + seq.length);
        if (sequenceKey(slice) === sequenceKey(seq)) {
          result.push({ type: 'pattern', ref_id: pattern.state.pattern_id });
          i += seq.length;
          matched = true;
          break;
        }
      }
    }

    if (!matched) {
      // No pattern match, emit single token
      result.push({ type: 'token', ref_id: tokenIds[i] });
      i++;
    }
  }

  return result;
}

export function compressPatternSequence(
  dict: DictionaryState,
  patternIds: string[]
): CompressedContent[] {
  const result: CompressedContent[] = [];
  let i = 0;

  while (i < patternIds.length) {
    let matched = false;

    // Try to match longest motif first
    const motifs = Array.from(dict.motifs.values())
      .sort((a, b) => b.state.pattern_sequence.length - a.state.pattern_sequence.length);

    for (const motif of motifs) {
      const seq = motif.state.pattern_sequence;
      if (i + seq.length <= patternIds.length) {
        const slice = patternIds.slice(i, i + seq.length);
        if (sequenceKey(slice) === sequenceKey(seq)) {
          result.push({ type: 'motif', ref_id: motif.state.motif_id });
          i += seq.length;
          matched = true;
          break;
        }
      }
    }

    if (!matched) {
      // No motif match, emit single pattern
      result.push({ type: 'pattern', ref_id: patternIds[i] });
      i++;
    }
  }

  return result;
}

// === DECOMPRESSION ===

export function expandToken(dict: DictionaryState, tokenId: string): string {
  const token = dict.tokens.get(tokenId);
  return token ? token.state.value : `[UNKNOWN:${tokenId}]`;
}

export function expandPattern(dict: DictionaryState, patternId: string): string {
  const pattern = dict.patterns.get(patternId);
  if (!pattern) return `[UNKNOWN:${patternId}]`;

  return pattern.state.token_sequence.map((tid) => expandToken(dict, tid)).join(' ');
}

export function expandMotif(
  dict: DictionaryState,
  motifId: string,
  params?: Record<string, string>
): string {
  const motif = dict.motifs.get(motifId);
  if (!motif) return `[UNKNOWN:${motifId}]`;

  let text = motif.state.pattern_sequence
    .map((pid) => expandPattern(dict, pid))
    .join(' ');

  // Replace slots with params
  if (params) {
    for (const [slot, value] of Object.entries(params)) {
      text = text.replace(`{${slot}}`, value);
    }
  }

  return text;
}

export function expandCompressed(
  dict: DictionaryState,
  content: CompressedContent
): string {
  switch (content.type) {
    case 'token':
      return expandToken(dict, content.ref_id);
    case 'pattern':
      return expandPattern(dict, content.ref_id);
    case 'motif':
      return expandMotif(dict, content.ref_id, content.params);
  }
}

export function expandCompressedSequence(
  dict: DictionaryState,
  sequence: CompressedContent[]
): string {
  return sequence.map((c) => expandCompressed(dict, c)).join(' ');
}

// === DISCOVERY ENGINE ===

export interface DiscoveryResult {
  newTokens: Array<{ entity: Entity; delta: Delta; state: TokenData }>;
  newPatterns: Array<{ entity: Entity; delta: Delta; state: PatternData }>;
  newMotifs: Array<{ entity: Entity; delta: Delta; state: MotifData }>;
  frequencyUpdates: Array<{ entity: Entity; delta: Delta }>;
  compressed: CompressedContent[];
}

export async function discoverAndCompress(
  dict: DictionaryState,
  text: string
): Promise<DiscoveryResult> {
  const newTokens: Array<{ entity: Entity; delta: Delta; state: TokenData }> = [];
  const newPatterns: Array<{ entity: Entity; delta: Delta; state: PatternData }> = [];
  const newMotifs: Array<{ entity: Entity; delta: Delta; state: MotifData }> = [];
  const frequencyUpdates: Array<{ entity: Entity; delta: Delta }> = [];

  // Step 1: Tokenize
  const { tokenIds, newTokenDeltas } = await tokenizeText(dict, text);
  newTokens.push(...newTokenDeltas);

  // Step 2: Extract patterns
  const patternResult = await extractPatterns(dict, tokenIds);
  newPatterns.push(...patternResult.promotedPatterns);
  frequencyUpdates.push(...patternResult.frequencyUpdates);

  // Step 3: Compress to patterns
  const compressedToPatterns = compressTokenSequence(dict, tokenIds);
  const patternIds = compressedToPatterns
    .filter((c) => c.type === 'pattern')
    .map((c) => c.ref_id);

  // Step 4: Extract motifs (if enough patterns)
  if (patternIds.length >= MIN_MOTIF_LENGTH) {
    const motifResult = await extractMotifs(dict, patternIds);
    newMotifs.push(...motifResult.promotedMotifs);
    frequencyUpdates.push(...motifResult.frequencyUpdates);
  }

  // Step 5: Final compression
  const compressed = compressPatternSequence(dict, patternIds);

  return {
    newTokens,
    newPatterns,
    newMotifs,
    frequencyUpdates,
    compressed,
  };
}

// === REWRITE OPERATIONS ===

export function buildRewritePatch(
  compressed: CompressedContent[]
): JsonPatch[] {
  // For entities that store template_id + params format
  if (compressed.length === 1 && compressed[0].type === 'motif') {
    return [
      { op: 'replace', path: '/template_id', value: compressed[0].ref_id },
      { op: 'replace', path: '/params', value: compressed[0].params || {} },
    ];
  }

  // For raw content, store as compressed sequence
  return [
    { op: 'replace', path: '/compressed_content', value: compressed },
  ];
}

// === COMPRESSION METRICS ===

export interface CompressionMetrics {
  total_tokens: number;
  total_patterns: number;
  total_motifs: number;
  unique_tokens: number;
  avg_pattern_length: number;
  avg_motif_length: number;
}

export function calculateMetrics(dict: DictionaryState): CompressionMetrics {
  const patterns = Array.from(dict.patterns.values());
  const motifs = Array.from(dict.motifs.values());

  const avgPatternLength =
    patterns.length > 0
      ? patterns.reduce((sum, p) => sum + p.state.token_sequence.length, 0) /
        patterns.length
      : 0;

  const avgMotifLength =
    motifs.length > 0
      ? motifs.reduce((sum, m) => sum + m.state.pattern_sequence.length, 0) /
        motifs.length
      : 0;

  return {
    total_tokens: Array.from(dict.tokens.values()).reduce(
      (sum, t) => sum + t.state.frequency,
      0
    ),
    total_patterns: patterns.reduce((sum, p) => sum + p.state.frequency, 0),
    total_motifs: motifs.reduce((sum, m) => sum + m.state.frequency, 0),
    unique_tokens: dict.tokens.size,
    avg_pattern_length: avgPatternLength,
    avg_motif_length: avgMotifLength,
  };
}

// === DELTA-DRIVEN TRIGGER ===

export function shouldTriggerDiscovery(delta: Delta): boolean {
  for (const patch of delta.patch) {
    // Trigger on new content
    if (
      patch.path.includes('template_id') ||
      patch.path.includes('params') ||
      patch.path.includes('title') ||
      patch.path.includes('content')
    ) {
      return true;
    }
  }
  return false;
}
