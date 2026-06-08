/**
 * Lattice projection layer - Atlas substrate -> lattice viewmodel.
 *
 * Slice 1 scope:
 *   - Read:  idea_registry.execute_now[] -> LatticeItem[]
 *   - Merge: user corrections (stored as `task` entities with
 *            cortex_metadata.source = 'lattice') override projected fields
 *   - Write: POST -> creates/updates task entity + appends to
 *            lattice_corrections.jsonl for cognitive-sensor's next run
 *
 * Provenance is the load-bearing field: every item carries
 * `provenance.source` so the right-click menu can show what
 * proposed the item before the user touched it.
 */

import { readFileSync, existsSync, appendFileSync } from 'fs';
import { join } from 'path';
import { z } from 'zod';
import { createEntity, now } from '../core/delta.js';
import type { TaskData, Entity } from '../core/types-core.js';

// === Viewmodel types (mirror lattice.html contract; string ids per option B) ===

export type LatticeStatus = 'open' | 'active' | 'blocked' | 'done' | 'dropped';
export type LatticeLinkKind = 'blocks' | 'spawned' | 'relates';
export type LatticeEventKind = 'add' | 'status' | 'link' | 'done';
export type LatticeProvenanceSource =
  | 'cognitive-sensor.idea_registry'
  | 'optogon'
  | 'user'
  | 'ghost_executor';

export interface LatticeLink {
  kind: LatticeLinkKind;
  to: string;
}

export interface LatticeProvenance {
  source: LatticeProvenanceSource;
  correctedFrom?: string;
  correctedAt?: string;
}

export interface LatticeItem {
  id: string;
  title: string;
  project: string;
  status: LatticeStatus;
  time: string;
  links: LatticeLink[];
  provenance: LatticeProvenance;
}

export interface LatticeProject {
  id: string;
  name: string;
}

export interface LatticeEvent {
  date: string;
  day: string;
  time: string;
  kind: LatticeEventKind;
  project: string;
  itemId: string;
  desc: string;
}

export type LatticeNodeType = 'item' | 'project';
export type LatticeEdgeKind = 'belongs_to' | 'blocks' | 'spawned' | 'relates';

export interface LatticeNode {
  id: string;
  type: LatticeNodeType;
  label: string;
  project?: string;
  status?: LatticeStatus;
  provenance?: LatticeProvenance;
}

export interface LatticeEdge {
  from: string;
  to: string;
  kind: LatticeEdgeKind;
}

export interface LatticeViewmodel {
  items: LatticeItem[];
  events: LatticeEvent[];
  projects: LatticeProject[];
  nodes: LatticeNode[];
  edges: LatticeEdge[];
}

// === Inference mappings (these are the corrigible heuristics) ===

const CATEGORY_TO_PROJECT: Record<string, string> = {
  ai_automation: 'atlas',
  business_strategy: 'optogon',
  productivity: 'inpact',
  property: 'property',
  music: 'music',
  lattice: 'lattice',
};

const PROJECTS: LatticeProject[] = [
  { id: 'lattice', name: 'lattice' },
  { id: 'optogon', name: 'optogon' },
  { id: 'atlas', name: 'atlas' },
  { id: 'inpact', name: 'inpact' },
  { id: 'property', name: 'property' },
  { id: 'music', name: 'music' },
];

function categoryToProject(category: string | undefined): string {
  if (!category) return 'atlas';
  return CATEGORY_TO_PROJECT[category] ?? 'atlas';
}

function tierToStatus(tier: string, registryStatus: string | undefined): LatticeStatus {
  if (registryStatus === 'started') return 'active';
  if (tier === 'execute_now') return 'active';
  if (tier === 'next_up') return 'open';
  if (tier === 'backlog') return 'open';
  if (tier === 'archive') return 'dropped';
  return 'open';
}

// === Idea registry shape (subset; tolerates missing fields) ===

interface IdeaRegistryEntry {
  canonical_id: string;
  canonical_title: string;
  category?: string;
  status?: string;
  dependencies?: string[];
  child_ideas?: string[];
}

interface IdeaRegistry {
  // Compact shape (cycleboard/brain/idea_registry.json) keeps tiers at top level
  execute_now?: IdeaRegistryEntry[];
  next_up?: IdeaRegistryEntry[];
  backlog?: IdeaRegistryEntry[];
  archive?: IdeaRegistryEntry[];
  // Full shape (services/cognitive-sensor/idea_registry.json) nests them
  tiers?: {
    execute_now?: IdeaRegistryEntry[];
    next_up?: IdeaRegistryEntry[];
    backlog?: IdeaRegistryEntry[];
    archive?: IdeaRegistryEntry[];
  };
  full_registry?: IdeaRegistryEntry[];
}

// Prefer the full registry at the cognitive-sensor root; fall back to the
// truncated cycleboard copy if the full one isn't present.
const REGISTRY_CANDIDATES = [
  'idea_registry.json',
  join('cycleboard', 'brain', 'idea_registry.json'),
];
const CORRECTIONS_FILENAME = 'lattice_corrections.jsonl';
const LATTICE_SOURCE_TAG = 'lattice';

function readRegistry(cognitiveSensorDir: string): IdeaRegistry | null {
  for (const rel of REGISTRY_CANDIDATES) {
    const path = join(cognitiveSensorDir, rel);
    if (!existsSync(path)) continue;
    try {
      return JSON.parse(readFileSync(path, 'utf-8')) as IdeaRegistry;
    } catch {
      // try next candidate
    }
  }
  return null;
}

// Normalize either registry shape so the rest of the code can read tiers
// off a single struct.
function tiersOf(registry: IdeaRegistry): {
  execute_now: IdeaRegistryEntry[];
  next_up: IdeaRegistryEntry[];
  backlog: IdeaRegistryEntry[];
  archive: IdeaRegistryEntry[];
} {
  const t = registry.tiers || registry;
  return {
    execute_now: t.execute_now || [],
    next_up: t.next_up || [],
    backlog: t.backlog || [],
    archive: t.archive || [],
  };
}

function buildItem(entry: IdeaRegistryEntry, tier: string): LatticeItem {
  const links: LatticeLink[] = [];
  for (const dep of entry.dependencies ?? []) {
    links.push({ kind: 'blocks', to: dep });
  }
  for (const child of entry.child_ideas ?? []) {
    links.push({ kind: 'spawned', to: child });
  }
  return {
    id: entry.canonical_id,
    title: entry.canonical_title,
    project: categoryToProject(entry.category),
    status: tierToStatus(tier, entry.status),
    time: 'recently',
    links,
    provenance: { source: 'cognitive-sensor.idea_registry' },
  };
}

// === Storage shim (mirrors Storage methods we use; keeps this module decoupled) ===

export interface StorageLike {
  loadEntitiesByType<T>(type: string): Array<{ entity: Entity; state: T }>;
  saveEntity(entity: Entity, state: unknown): void;
  appendDelta(delta: unknown): void;
}

interface LatticeCorrectionMeta {
  source: 'lattice';
  lattice_item_id: string;
  original_project?: string;
  original_status?: string;
  corrected_at: string;
}

const VALID_STATUSES: ReadonlySet<LatticeStatus> = new Set([
  'open', 'active', 'blocked', 'done', 'dropped',
]);

function isLatticeCorrectionMeta(meta: unknown): meta is LatticeCorrectionMeta {
  if (typeof meta !== 'object' || meta === null) return false;
  const m = meta as Record<string, unknown>;
  return m.source === LATTICE_SOURCE_TAG && typeof m.lattice_item_id === 'string';
}

interface UserCorrection {
  project?: string;
  status?: LatticeStatus;
  originalProject: string;
  originalStatus: string;
  correctedAt: string;
}

function collectCorrections(storage: StorageLike): Map<string, UserCorrection> {
  const corrections = new Map<string, UserCorrection>();
  const taskEntities = storage.loadEntitiesByType<Record<string, unknown>>('task');
  for (const e of taskEntities) {
    const state = e.state as Record<string, unknown>;
    const meta = state.cortex_metadata;
    if (!isLatticeCorrectionMeta(meta)) continue;
    const project = typeof state.project === 'string' ? state.project : undefined;
    const latticeStatus =
      typeof state.lattice_status === 'string' &&
      VALID_STATUSES.has(state.lattice_status as LatticeStatus)
        ? (state.lattice_status as LatticeStatus)
        : undefined;
    if (!project && !latticeStatus) continue;
    corrections.set(meta.lattice_item_id, {
      project,
      status: latticeStatus,
      originalProject: meta.original_project ?? '',
      originalStatus: meta.original_status ?? '',
      correctedAt: meta.corrected_at,
    });
  }
  return corrections;
}

// === Public API ===

export function buildViewmodel(
  cognitiveSensorDir: string,
  storage: StorageLike,
): LatticeViewmodel {
  const registry = readRegistry(cognitiveSensorDir);
  const items: LatticeItem[] = [];

  const tiers = registry ? tiersOf(registry) : null;
  if (tiers) {
    for (const entry of tiers.execute_now) {
      items.push(buildItem(entry, 'execute_now'));
    }
  }

  // Data-light projection of every OTHER known idea so the graph can render
  // link targets (canon_0250's 23 spawned children, etc.) with real titles
  // instead of "#0249" ghost stubs. Prefer `full_registry` (1339 entries)
  // when present; fall back to whatever tier arrays exist.
  const lookupItems: IdeaRegistryEntry[] = [];
  if (registry?.full_registry && Array.isArray(registry.full_registry)) {
    for (const entry of registry.full_registry) lookupItems.push(entry);
  } else if (tiers) {
    for (const tier of ['next_up', 'backlog', 'archive'] as const) {
      for (const entry of tiers[tier]) lookupItems.push(entry);
    }
  }

  // Apply user corrections (override layer)
  const corrections = collectCorrections(storage);
  for (const item of items) {
    const correction = corrections.get(item.id);
    if (!correction) continue;
    const projectedProject = item.project;
    const projectedStatus = item.status;
    const correctedFromParts: string[] = [];
    if (correction.project && correction.project !== projectedProject) {
      item.project = correction.project;
      correctedFromParts.push(`project=${correction.originalProject || projectedProject}`);
    }
    if (correction.status && correction.status !== projectedStatus) {
      item.status = correction.status;
      correctedFromParts.push(`status=${correction.originalStatus || projectedStatus}`);
    }
    item.provenance = {
      source: 'user',
      correctedFrom: correctedFromParts.join(', ') || correction.originalProject || projectedProject,
      correctedAt: correction.correctedAt,
    };
  }

  // === Graph projection ===
  // Same data as items/projects, restated as nodes + edges so any view
  // can read the canonical structure (tree, graph, timeline, future views).
  const nodes: LatticeNode[] = [];
  const edges: LatticeEdge[] = [];

  // Project nodes (hubs)
  for (const p of PROJECTS) {
    nodes.push({ id: 'project:' + p.id, type: 'project', label: p.name });
  }
  // Item nodes + belongs-to edges
  for (const it of items) {
    nodes.push({
      id: it.id,
      type: 'item',
      label: it.title,
      project: it.project,
      status: it.status,
      provenance: it.provenance,
    });
    edges.push({ from: it.id, to: 'project:' + it.project, kind: 'belongs_to' });
  }
  // Inter-item edges from item.links (may point to ids outside the current
  // item set; the consumer can render them as ghost nodes or filter).
  for (const it of items) {
    for (const link of it.links) {
      edges.push({ from: it.id, to: link.to, kind: link.kind });
    }
  }

  // Lookup-only nodes for the other tiers (title + project derived from
  // category). No edges. Lets the graph show real titles for link targets.
  const seenIds = new Set(nodes.map((n) => n.id));
  for (const entry of lookupItems) {
    if (seenIds.has(entry.canonical_id)) continue;
    seenIds.add(entry.canonical_id);
    nodes.push({
      id: entry.canonical_id,
      type: 'item',
      label: entry.canonical_title,
      project: categoryToProject(entry.category),
      status: 'open',
      provenance: { source: 'cognitive-sensor.idea_registry' },
    });
  }

  return { items, events: [], projects: PROJECTS, nodes, edges };
}

export interface CorrectionRequest {
  id: string;
  project?: string;
  status?: LatticeStatus;
  originalProject?: string;
  originalStatus?: string;
  originalTitle?: string;
}

export interface CorrectionResult {
  taskId: string;
  correctedAt: string;
}

export class CorrectionValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CorrectionValidationError';
  }
}

// Zod schema replaces the hand-rolled type-check + enum-check pyramid.
// Refines for the cross-field rule ("project OR status required").
const PROJECT_IDS = PROJECTS.map((p) => p.id) as [string, ...string[]];
const STATUS_VALUES = Array.from(VALID_STATUSES) as [LatticeStatus, ...LatticeStatus[]];
const CorrectionRequestZ = z
  .object({
    id: z.string().min(1),
    project: z.enum(PROJECT_IDS).optional(),
    status: z.enum(STATUS_VALUES).optional(),
    originalProject: z.string().optional(),
    originalStatus: z.string().optional(),
    originalTitle: z.string().optional(),
  })
  .refine((p) => p.project !== undefined || p.status !== undefined, {
    message: 'Payload must include at least one of "project" or "status"',
  });

function validateCorrection(payload: unknown): CorrectionRequest {
  const parsed = CorrectionRequestZ.safeParse(payload);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    throw new CorrectionValidationError(first?.message ?? 'Invalid correction payload');
  }
  return parsed.data;
}

export async function recordCorrection(
  cognitiveSensorDir: string,
  storage: StorageLike,
  rawPayload: unknown,
): Promise<CorrectionResult> {
  const payload = validateCorrection(rawPayload);
  const correctedAt = new Date(now()).toISOString();

  // Look for an existing correction task for this lattice id
  const taskEntities = storage.loadEntitiesByType<Record<string, unknown>>('task');
  let existing: { entity: Entity; state: Record<string, unknown> } | undefined;
  for (const e of taskEntities) {
    const meta = e.state.cortex_metadata;
    if (isLatticeCorrectionMeta(meta) && meta.lattice_item_id === payload.id) {
      existing = e;
      break;
    }
  }

  let taskId: string;

  if (existing) {
    const state = existing.state;
    const prevMeta = isLatticeCorrectionMeta(state.cortex_metadata)
      ? state.cortex_metadata
      : null;
    const updatedState: Record<string, unknown> = {
      ...state,
      cortex_metadata: {
        source: LATTICE_SOURCE_TAG,
        lattice_item_id: payload.id,
        original_project:
          prevMeta?.original_project ?? payload.originalProject ?? '',
        original_status:
          prevMeta?.original_status ?? payload.originalStatus ?? '',
        corrected_at: correctedAt,
      },
    };
    if (payload.project !== undefined) updatedState.project = payload.project;
    if (payload.status !== undefined) updatedState.lattice_status = payload.status;
    storage.saveEntity(existing.entity, updatedState);
    taskId = existing.entity.entity_id;
  } else {
    const taskData: TaskData = {
      title_template: payload.originalTitle ?? `lattice:${payload.id}`,
      title_params: {},
      status: 'OPEN',
      priority: 'NORMAL',
      due_at: null,
      linked_thread: null,
    };
    const result = await createEntity('task', taskData);
    const seededState: Record<string, unknown> = {
      ...(result.state as Record<string, unknown>),
      cortex_metadata: {
        source: LATTICE_SOURCE_TAG,
        lattice_item_id: payload.id,
        original_project: payload.originalProject ?? '',
        original_status: payload.originalStatus ?? '',
        corrected_at: correctedAt,
      },
    };
    if (payload.project !== undefined) seededState.project = payload.project;
    if (payload.status !== undefined) seededState.lattice_status = payload.status;
    storage.saveEntity(result.entity, seededState);
    storage.appendDelta(result.delta);
    taskId = result.entity.entity_id;
  }

  // Append to substrate-readable corrections log
  const correctionsPath = join(cognitiveSensorDir, CORRECTIONS_FILENAME);
  const correctionRecord = {
    schema_version: '1.1',
    id: payload.id,
    project: payload.project ?? null,
    status: payload.status ?? null,
    original_project: payload.originalProject ?? '',
    original_status: payload.originalStatus ?? '',
    corrected_at: correctedAt,
    task_entity_id: taskId,
  };
  appendFileSync(correctionsPath, JSON.stringify(correctionRecord) + '\n', 'utf-8');

  return { taskId, correctedAt };
}
