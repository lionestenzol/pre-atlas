/**
 * Delta-State Fabric — API Server
 *
 * Shared backend for CLI and web app.
 * Stores data in ~/.delta-fabric/
 */

import express from 'express';
import cors from 'cors';
import { Storage } from '../cli/storage';
import { createEntity, createDelta, now } from '../core/delta';
import { getDaemon, JobName } from '../governance/governance_daemon';
import { WorkController } from '../core/work-controller';
import { getTimelineLogger } from '../core/timeline-logger.js';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

// ES Module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3001;

// Storage
const dataDir = process.env.DELTA_DATA_DIR || path.join(os.homedir(), '.delta-fabric');
const storage = new Storage({ dataDir });

// Repo root (for daemon)
const repoRoot = process.env.DELTA_DATA_DIR
  ? path.resolve(process.env.DELTA_DATA_DIR, '..')
  : path.resolve(__dirname, '../../../../..');

// Initialize and start governance daemon
const daemon = getDaemon(storage, repoRoot);
daemon.start();

// Initialize work controller
const workController = new WorkController(repoRoot);

// Initialize timeline logger
const timeline = getTimelineLogger(repoRoot);

app.use(cors());
app.use(express.json());

// Serve control panel UI
app.use('/control', express.static(path.join(__dirname, '../ui')));

// === UNIFIED STATE (must be before /api/state to avoid route conflict) ===

/**
 * GET /api/state/unified
 * Single truth payload merging Delta authoritative state + cognitive snapshots.
 * Gracefully handles missing files.
 */
app.get('/api/state/unified', (req, res) => {
  const errors: string[] = [];

  // A) Load Delta authoritative state
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  const deltaState = entities.length > 0 ? entities[0].state : null;

  // B) Determine repo root (go up from delta-kernel/src/api to repo root)
  const repoRoot = process.env.DELTA_DATA_DIR
    ? path.resolve(process.env.DELTA_DATA_DIR, '..')
    : path.resolve(__dirname, '../../../../..');

  // Helper to safely read JSON files
  const readJsonFile = (filePath: string, name: string): unknown | null => {
    try {
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
      } else {
        errors.push(`${name} not found`);
        return null;
      }
    } catch (e) {
      errors.push(`${name} read error: ${(e as Error).message}`);
      return null;
    }
  };

  // C) Read cognitive snapshot files
  const cognitiveStatePath = path.join(repoRoot, 'services/cognitive-sensor/cognitive_state.json');
  const loopsLatestPath = path.join(repoRoot, 'services/cognitive-sensor/loops_latest.json');
  const todayPath = path.join(repoRoot, 'data/projections/today.json');
  const closuresPath = path.join(repoRoot, 'services/cognitive-sensor/closures.json');

  const cognitiveState = readJsonFile(cognitiveStatePath, 'cognitive_state.json') as Record<string, unknown> | null;
  const loopsLatest = readJsonFile(loopsLatestPath, 'loops_latest.json') as unknown[] | null;
  const today = readJsonFile(todayPath, 'today.json') as Record<string, unknown> | null;
  const closuresRegistry = readJsonFile(closuresPath, 'closures.json') as { closures: unknown[]; stats: Record<string, unknown> } | null;

  // D) Derive unified values (prefer cognitive files → delta state → defaults)
  const todayDirective = today?.directive as Record<string, unknown> | undefined;
  const todayCognitive = today?.cognitive as Record<string, unknown> | undefined;

  // Mode: today.json > delta state > default
  const mode = (todayDirective?.mode as string)
    ?? (deltaState?.mode as string)
    ?? 'RECOVER';

  // Risk: today.json > delta state > default
  const risk = (todayDirective?.risk as string)
    ?? (deltaState?.risk as string)
    ?? 'MEDIUM';

  // Open loops: cognitive_state > today.json > delta state > default
  const closureData = cognitiveState?.closure as Record<string, unknown> | undefined;
  const openLoops = (closureData?.open as number)
    ?? (todayCognitive?.closure as Record<string, unknown>)?.open as number
    ?? (deltaState?.open_loops as number)
    ?? 0;

  // Closure ratio: cognitive_state > today.json > delta state > default
  const closureRatio = (closureData?.ratio as number)
    ?? (todayCognitive?.closure as Record<string, unknown>)?.ratio as number
    ?? (deltaState?.closure_ratio as number)
    ?? 0;

  // Primary order: today.json > delta state > default
  const primaryOrder = (todayDirective?.primary_action as string)
    ?? (deltaState?.primary_action as string)
    ?? 'Run refresh to get today\'s order';

  // Build allowed: today.json > delta state > compute from mode
  const buildAllowedFromDirective = todayDirective?.build_allowed as boolean | undefined;
  const buildAllowedFromDelta = deltaState?.build_allowed as boolean | undefined;
  // Default: build allowed unless mode is CLOSURE
  const buildAllowed = buildAllowedFromDirective
    ?? buildAllowedFromDelta
    ?? (mode !== 'CLOSURE');

  // Enforcement state from delta
  const enforcement = (deltaState?.enforcement as Record<string, unknown>) || {};
  const violationsCount = (enforcement.violations_count as number) || 0;
  const overridesCount = (enforcement.overrides_count as number) || 0;
  // Compute enforcement level: 0→0, 1→1, 2→2, >=3→3
  const enforcementLevel = Math.min(violationsCount, 3);
  // Override is available unless at max enforcement
  const overrideAvailable = enforcementLevel < 3 || overridesCount === 0;

  // Closure stats from registry
  const closureStats = closuresRegistry?.stats || {};
  const closuresToday = (closureStats.closures_today as number) || 0;
  const totalClosures = (closureStats.total_closures as number) || 0;
  const streakDays = (closureStats.streak_days as number) ?? (deltaState?.streak_days as number) ?? 0;
  const bestStreak = (closureStats.best_streak as number) || 0;

  res.json({
    ok: true,
    ts: new Date().toISOString(),
    delta: {
      system_state: deltaState,
    },
    cognitive: {
      cognitive_state: cognitiveState,
      loops_latest: loopsLatest,
      today: today,
      closures: closuresRegistry,
    },
    derived: {
      mode,
      risk,
      open_loops: openLoops,
      closure_ratio: closureRatio,
      primary_order: primaryOrder,
      build_allowed: buildAllowed,
      enforcement_level: enforcementLevel,
      violations_count: violationsCount,
      overrides_count: overridesCount,
      override_available: overrideAvailable,
      // Closure metrics for cockpit
      closures_today: closuresToday,
      total_closures: totalClosures,
      streak_days: streakDays,
      best_streak: bestStreak,
    },
    errors,
  });
});

// === STATE ===

interface SimpleState {
  mode: string;
  sleepHours: number;
  openLoops: number;
  leverageBalance: number;
  streakDays: number;
}

// Get system state
app.get('/api/state', (req, res) => {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length === 0) {
    // Return default state
    res.json({
      mode: 'RECOVER',
      sleepHours: 6,
      openLoops: 0,
      leverageBalance: 0,
      streakDays: 0,
    });
    return;
  }

  const state = entities[0].state;
  res.json({
    mode: state.mode || 'RECOVER',
    sleepHours: state.sleep_hours ?? state.sleepHours ?? 6,
    openLoops: state.open_loops ?? state.openLoops ?? 0,
    leverageBalance: state.leverage_balance ?? state.leverageBalance ?? 0,
    streakDays: state.streak_days ?? state.streakDays ?? 0,
  });
});

// Update system state
app.put('/api/state', async (req, res) => {
  const newState: SimpleState = req.body;

  const stateData = {
    mode: newState.mode as import('../core/types').Mode,
    sleep_hours: newState.sleepHours,
    open_loops: newState.openLoops,
    leverage_balance: newState.leverageBalance,
    streak_days: newState.streakDays,
  };

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length > 0) {
    // Update existing
    const existing = entities[0];
    const result = await createDelta(
      existing.entity,
      existing.state,
      Object.entries(stateData).map(([key, value]) => ({
        op: 'replace' as const,
        path: `/${key}`,
        value,
      })),
      'user'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    // Create new
    const result = await createEntity('system_state', stateData);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({ success: true });
});

// === TASKS ===

interface TaskResponse {
  id: string;
  title: string;
  status: string;
  priority: string;
  createdAt: number;
}

// Get all tasks
app.get('/api/tasks', (req, res) => {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('task');

  const tasks: TaskResponse[] = entities.map(e => ({
    id: e.entity.entity_id,
    title: (e.state.title as string) || '',
    status: (e.state.status as string) || 'OPEN',
    priority: (e.state.priority as string) || 'NORMAL',
    createdAt: e.entity.created_at,
  }));

  res.json(tasks);
});

// Create task
app.post('/api/tasks', async (req, res) => {
  const { title, priority = 'NORMAL' } = req.body;

  if (!title) {
    res.status(400).json({ error: 'Title required' });
    return;
  }

  const taskData = {
    title,
    status: 'OPEN' as import('../core/types').TaskStatus,
    priority: priority as import('../core/types').Priority,
    created_at: now(),
    due_at: null,
    closed_at: null,
    project_id: null,
    parent_task_id: null,
    template_id: null,
    params: {},
  };

  const result = await createEntity('task', taskData);
  storage.saveEntity(result.entity, result.state);
  storage.appendDelta(result.delta);

  res.json({
    id: result.entity.entity_id,
    title,
    status: 'OPEN',
    priority,
    createdAt: result.entity.created_at,
  });
});

// Update task
app.put('/api/tasks/:id', async (req, res) => {
  const { id } = req.params;
  const updates = req.body;

  const entities = storage.loadAllEntities();
  let found = false;

  for (const [_, data] of entities) {
    if (data.entity.entity_id === id) {
      const state = data.state as Record<string, unknown>;

      if (updates.status) state.status = updates.status;
      if (updates.priority) state.priority = updates.priority;
      if (updates.status === 'DONE') state.closed_at = now();

      storage.saveEntity(data.entity, state);
      found = true;
      break;
    }
  }

  if (!found) {
    res.status(404).json({ error: 'Task not found' });
    return;
  }

  res.json({ success: true });
});

// Delete task
app.delete('/api/tasks/:id', (req, res) => {
  const { id } = req.params;

  // For now, mark as archived (we don't actually delete in delta-driven systems)
  const entities = storage.loadAllEntities();

  for (const [_, data] of entities) {
    if (data.entity.entity_id === id) {
      const state = data.state as Record<string, unknown>;
      state.status = 'ARCHIVED';
      storage.saveEntity(data.entity, state);
      break;
    }
  }

  res.json({ success: true });
});

// === INGEST ===

/**
 * Ingest cognitive metrics from cognitive-sensor.
 * Updates system_state with open_loops and computed mode.
 */
app.post('/api/ingest/cognitive', async (req, res) => {
  const projection = req.body;

  // Validate required fields
  if (!projection.cognitive || !projection.directive) {
    res.status(400).json({ error: 'Invalid projection: missing cognitive or directive' });
    return;
  }

  const { cognitive, directive } = projection;

  // Map to system_state format (partial - uses any cast for flexibility)
  const stateData: Record<string, unknown> = {
    mode: directive.mode,
    open_loops: cognitive.closure?.open ?? directive.open_loop_count ?? 0,
    closure_ratio: cognitive.closure?.ratio ?? directive.closure_ratio ?? 0,
    risk: directive.risk,
    build_allowed: directive.build_allowed,
    primary_action: directive.primary_action,
    last_ingest: now(),
  };

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length > 0) {
    // Update existing
    const existing = entities[0];
    const result = await createDelta(
      existing.entity,
      existing.state,
      Object.entries(stateData).map(([key, value]) => ({
        op: 'replace' as const,
        path: `/${key}`,
        value,
      })),
      'cognitive-sensor'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    // Create new (cast since cognitive state differs from full SystemStateData)
    const result = await createEntity('system_state', stateData as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({
    success: true,
    mode: stateData.mode,
    open_loops: stateData.open_loops,
  });
});

// === LAW ENDPOINTS ===

/**
 * POST /api/law/acknowledge
 * User acknowledges today's order. Records timestamp and order text.
 */
app.post('/api/law/acknowledge', async (req, res) => {
  const { order } = req.body;

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  const acknowledgeData = {
    last_acknowledged_at: now(),
    last_acknowledged_order: order || 'Order acknowledged',
  };

  if (entities.length > 0) {
    const existing = entities[0];
    const result = await createDelta(
      existing.entity,
      existing.state,
      Object.entries(acknowledgeData).map(([key, value]) => ({
        op: 'replace' as const,
        path: `/${key}`,
        value,
      })),
      'user'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    const result = await createEntity('system_state', acknowledgeData as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({
    success: true,
    acknowledged_at: acknowledgeData.last_acknowledged_at,
  });
});

/**
 * POST /api/law/archive
 * Archive a loop. Appends to archived_loops array with timestamp.
 */
app.post('/api/law/archive', async (req, res) => {
  const { loop_id, loop_title, reason } = req.body;

  if (!loop_id && !loop_title) {
    res.status(400).json({ error: 'loop_id or loop_title required' });
    return;
  }

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  const archiveEntry = {
    loop_id: loop_id || null,
    loop_title: loop_title || null,
    reason: reason || 'Archived via ATLAS cockpit',
    archived_at: now(),
  };

  if (entities.length > 0) {
    const existing = entities[0];
    const currentArchived = (existing.state.archived_loops as unknown[]) || [];
    const newArchived = [...currentArchived, archiveEntry];

    const result = await createDelta(
      existing.entity,
      existing.state,
      [{ op: 'replace' as const, path: '/archived_loops', value: newArchived }],
      'user'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    const result = await createEntity('system_state', { archived_loops: [archiveEntry] } as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({
    success: true,
    archived: archiveEntry,
  });
});

/**
 * POST /api/law/refresh
 * Request a cognitive sensor refresh. Records timestamp.
 * Does not spawn Python directly - caller handles that.
 */
app.post('/api/law/refresh', async (req, res) => {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  const refreshData = {
    last_refresh_requested_at: now(),
  };

  if (entities.length > 0) {
    const existing = entities[0];
    const result = await createDelta(
      existing.entity,
      existing.state,
      [{ op: 'replace' as const, path: '/last_refresh_requested_at', value: refreshData.last_refresh_requested_at }],
      'user'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    const result = await createEntity('system_state', refreshData as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({
    success: true,
    refresh_requested_at: refreshData.last_refresh_requested_at,
  });
});

/**
 * POST /api/law/violation
 * Log a build violation when user attempts build action while locked.
 * Uses leaf-patch deltas to avoid clobbering sibling enforcement fields.
 * Body: { action: string, context?: object }
 */
app.post('/api/law/violation', async (req, res) => {
  const { action, context } = req.body;

  if (!action) {
    res.status(400).json({ error: 'action is required' });
    return;
  }

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  const timestamp = now();

  const violationEntry = {
    ts: timestamp,
    action,
    context: context || null,
  };

  if (entities.length > 0) {
    const existing = entities[0];
    const enforcement = (existing.state.enforcement as Record<string, unknown>) || null;
    const currentViolations = enforcement ? (enforcement.violations_count as number) || 0 : 0;
    const currentLog = enforcement ? (enforcement.violation_log as unknown[]) || [] : [];
    const newViolationsCount = currentViolations + 1;

    // Build patches - create enforcement if it doesn't exist, otherwise leaf-patch
    const patches: Array<{ op: 'replace' | 'add'; path: string; value: unknown }> = [];

    if (!enforcement) {
      // Create enforcement object with violation
      patches.push({
        op: 'add',
        path: '/enforcement',
        value: {
          violations_count: 1,
          last_violation_at: timestamp,
          violation_log: [violationEntry],
          overrides_count: 0,
          override_log: [],
          closure_log: [],
        },
      });
    } else {
      // Leaf-patch existing enforcement
      patches.push({ op: 'replace', path: '/enforcement/violations_count', value: newViolationsCount });
      patches.push({ op: 'replace', path: '/enforcement/last_violation_at', value: timestamp });
      patches.push({ op: 'replace', path: '/enforcement/violation_log', value: [...currentLog, violationEntry] });
    }

    const result = await createDelta(
      existing.entity,
      existing.state,
      patches,
      'enforcement_system'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      violations_count: enforcement ? newViolationsCount : 1,
      enforcement_level: Math.min(enforcement ? newViolationsCount : 1, 3),
    });
  } else {
    const newEnforcement = {
      violations_count: 1,
      last_violation_at: timestamp,
      violation_log: [violationEntry],
      overrides_count: 0,
      override_log: [],
      closure_log: [],
    };
    const result = await createEntity('system_state', { enforcement: newEnforcement } as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      violations_count: 1,
      enforcement_level: 1,
    });
  }
});

/**
 * POST /api/law/override
 * Log an override when user bypasses enforcement.
 * Uses leaf-patch deltas to avoid clobbering sibling enforcement fields.
 * Body: { reason: string }
 */
app.post('/api/law/override', async (req, res) => {
  const { reason } = req.body;

  if (!reason) {
    res.status(400).json({ error: 'reason is required' });
    return;
  }

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  const timestamp = now();

  const overrideEntry = {
    ts: timestamp,
    reason,
  };

  if (entities.length > 0) {
    const existing = entities[0];
    const enforcement = (existing.state.enforcement as Record<string, unknown>) || null;
    const currentOverrides = enforcement ? (enforcement.overrides_count as number) || 0 : 0;
    const currentLog = enforcement ? (enforcement.override_log as unknown[]) || [] : [];
    const newOverridesCount = currentOverrides + 1;

    // Build patches - create enforcement if it doesn't exist, otherwise leaf-patch
    const patches: Array<{ op: 'replace' | 'add'; path: string; value: unknown }> = [];

    if (!enforcement) {
      // Create enforcement object with override
      patches.push({
        op: 'add',
        path: '/enforcement',
        value: {
          violations_count: 0,
          violation_log: [],
          overrides_count: 1,
          last_override_at: timestamp,
          override_log: [overrideEntry],
          closure_log: [],
        },
      });
    } else {
      // Leaf-patch existing enforcement
      patches.push({ op: 'replace', path: '/enforcement/overrides_count', value: newOverridesCount });
      patches.push({ op: 'replace', path: '/enforcement/last_override_at', value: timestamp });
      patches.push({ op: 'replace', path: '/enforcement/override_log', value: [...currentLog, overrideEntry] });
    }

    const result = await createDelta(
      existing.entity,
      existing.state,
      patches,
      'enforcement_system'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      overrides_count: enforcement ? newOverridesCount : 1,
      override_logged: true,
    });
  } else {
    const newEnforcement = {
      violations_count: 0,
      violation_log: [],
      overrides_count: 1,
      last_override_at: timestamp,
      override_log: [overrideEntry],
      closure_log: [],
    };
    const result = await createEntity('system_state', { enforcement: newEnforcement } as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      overrides_count: 1,
      override_logged: true,
    });
  }
});

/**
 * POST /api/law/close_loop
 * PHASE 5B — CANONICAL CLOSURE EVENT
 *
 * Atomic closure law that performs in ONE delta:
 * - Enforcement reset (violations_count → 0)
 * - Metrics mutation (closed_loops_total++, closure_ratio, last_closure_at)
 * - BUILD-only streak increment (no inflation)
 * - Mode transition if ratio crosses threshold
 * - Physical loop removal hooks (Step 5)
 *
 * Body: { loop_id?: string, title?: string, outcome: "closed"|"archived" }
 *
 * Idempotency: duplicate closures (same loop_id) are rejected.
 */
app.post('/api/law/close_loop', async (req, res) => {
  const { loop_id, title, outcome } = req.body;

  if (!outcome || (outcome !== 'closed' && outcome !== 'archived')) {
    res.status(400).json({ error: 'outcome must be "closed" or "archived"' });
    return;
  }

  const timestamp = now();
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayStartTs = todayStart.getTime();
  const todayStr = todayStart.toISOString().split('T')[0];

  // === A) COGNITIVE REGISTRY — closures.json ===
  const closuresPath = path.join(repoRoot, 'services/cognitive-sensor/closures.json');
  let closuresRegistry: {
    closures: Array<{ ts: number; loop_id: string | null; title: string | null; outcome: string }>;
    stats: {
      total_closures: number;
      closures_today: number;
      last_closure_at: number | null;
      streak_days: number;
      last_streak_date: string | null;
      best_streak: number;
    };
  };

  try {
    if (fs.existsSync(closuresPath)) {
      closuresRegistry = JSON.parse(fs.readFileSync(closuresPath, 'utf-8'));
    } else {
      closuresRegistry = {
        closures: [],
        stats: { total_closures: 0, closures_today: 0, last_closure_at: null, streak_days: 0, last_streak_date: null, best_streak: 0 },
      };
    }
  } catch {
    closuresRegistry = {
      closures: [],
      stats: { total_closures: 0, closures_today: 0, last_closure_at: null, streak_days: 0, last_streak_date: null, best_streak: 0 },
    };
  }

  // === E) IDEMPOTENCY CHECK ===
  // If loop_id provided, check for duplicate closure
  if (loop_id) {
    const alreadyClosed = closuresRegistry.closures.some(c => c.loop_id === loop_id);
    if (alreadyClosed) {
      res.status(409).json({
        success: false,
        error: 'already_closed',
        message: `Loop ${loop_id} has already been closed`,
        loop_id,
      });
      return;
    }
  }

  // Build closure entry
  const closureEntry = {
    ts: timestamp,
    loop_id: loop_id || null,
    title: title || null,
    outcome,
  };

  // Append to registry
  closuresRegistry.closures.push(closureEntry);
  closuresRegistry.stats.total_closures += 1;
  closuresRegistry.stats.last_closure_at = timestamp;

  // Count closures today
  const closuresToday = closuresRegistry.closures.filter(c => c.ts >= todayStartTs).length;
  closuresRegistry.stats.closures_today = closuresToday;

  // === B) READ COGNITIVE STATE FOR RATIO COMPUTATION ===
  const cognitiveStatePath = path.join(repoRoot, 'services/cognitive-sensor/cognitive_state.json');
  let openLoops = 0;

  try {
    if (fs.existsSync(cognitiveStatePath)) {
      const cogState = JSON.parse(fs.readFileSync(cognitiveStatePath, 'utf-8'));
      openLoops = cogState.closure?.open ?? 0;
    }
  } catch {
    // Use default
  }

  // Closure ratio = closed / (open + closed)
  const closedLoops = closuresRegistry.stats.total_closures;
  const totalLoops = openLoops + closedLoops;
  const closureRatio = totalLoops > 0 ? closedLoops / totalLoops : 1;

  // === MODE TRANSITION RULES ===
  let newMode: string;
  let buildAllowed: boolean;
  if (closureRatio >= 0.8) {
    newMode = 'SCALE';
    buildAllowed = true;
  } else if (closureRatio >= 0.6) {
    newMode = 'BUILD';
    buildAllowed = true;
  } else if (closureRatio >= 0.4) {
    newMode = 'MAINTENANCE';
    buildAllowed = false;
  } else {
    newMode = 'CLOSURE';
    buildAllowed = false;
  }

  // === C) BUILD-ONLY STREAK INCREMENT ===
  // Streak ONLY increments if current mode is BUILD (or will be BUILD after this closure)
  // AND this is the first closure of the day
  let streakUpdated = false;
  const isFirstClosureToday = closuresRegistry.stats.last_streak_date !== todayStr;

  if (isFirstClosureToday && (newMode === 'BUILD' || newMode === 'SCALE')) {
    closuresRegistry.stats.last_streak_date = todayStr;
    closuresRegistry.stats.streak_days += 1;
    streakUpdated = true;
    if (closuresRegistry.stats.streak_days > closuresRegistry.stats.best_streak) {
      closuresRegistry.stats.best_streak = closuresRegistry.stats.streak_days;
    }
  }

  // Write closures registry (durable)
  const closuresDir = path.dirname(closuresPath);
  if (!fs.existsSync(closuresDir)) {
    fs.mkdirSync(closuresDir, { recursive: true });
  }
  fs.writeFileSync(closuresPath, JSON.stringify(closuresRegistry, null, 2));

  // === D) PHYSICAL LOOP CLOSURE HOOKS (Step 5 completion) ===
  // Remove from loops_latest.json, append to loops_closed.json
  if (loop_id) {
    const loopsLatestPath = path.join(repoRoot, 'services/cognitive-sensor/loops_latest.json');
    const loopsClosedPath = path.join(repoRoot, 'services/cognitive-sensor/loops_closed.json');

    try {
      // Remove from loops_latest.json
      if (fs.existsSync(loopsLatestPath)) {
        const loopsLatest = JSON.parse(fs.readFileSync(loopsLatestPath, 'utf-8')) as Array<{ id?: string; loop_id?: string; title?: string }>;
        const filteredLoops = loopsLatest.filter(l => l.id !== loop_id && l.loop_id !== loop_id);
        if (filteredLoops.length !== loopsLatest.length) {
          fs.writeFileSync(loopsLatestPath, JSON.stringify(filteredLoops, null, 2));
        }
      }

      // Append to loops_closed.json
      let loopsClosed: Array<{ loop_id: string; title: string | null; closed_at: number; outcome: string }> = [];
      if (fs.existsSync(loopsClosedPath)) {
        loopsClosed = JSON.parse(fs.readFileSync(loopsClosedPath, 'utf-8'));
      }
      loopsClosed.push({
        loop_id,
        title: title || null,
        closed_at: timestamp,
        outcome,
      });
      fs.writeFileSync(loopsClosedPath, JSON.stringify(loopsClosed, null, 2));
    } catch (e) {
      // Physical closure is best-effort; log but don't fail the request
      console.error('[close_loop] Physical loop removal failed:', (e as Error).message);
    }
  }

  // === ATOMIC DELTA — LEAF PATCHES ONLY ===
  // Law Genesis Layer ensures all paths auto-materialize
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length > 0) {
    const existing = entities[0];
    const currentMode = (existing.state.mode as string) || 'CLOSURE';
    const currentMetrics = (existing.state.metrics as Record<string, unknown>) || {};
    const currentEnforcement = (existing.state.enforcement as Record<string, unknown>) || {};
    const currentClosureLog = (currentEnforcement.closure_log as unknown[]) || [];
    const currentClosedTotal = (currentMetrics.closed_loops_total as number) || 0;
    const currentStreakDays = (existing.state.streak_days as number) || 0;

    // All leaf patches in ONE atomic delta
    const patches: Array<{ op: 'replace'; path: string; value: unknown }> = [
      // Enforcement reset
      { op: 'replace', path: '/enforcement/violations_count', value: 0 },
      { op: 'replace', path: '/enforcement/closure_log', value: [...currentClosureLog, closureEntry] },

      // Metrics mutation
      { op: 'replace', path: '/metrics/closed_loops_total', value: currentClosedTotal + 1 },
      { op: 'replace', path: '/metrics/last_closure_at', value: timestamp },
      { op: 'replace', path: '/metrics/closure_ratio', value: closureRatio },
      { op: 'replace', path: '/metrics/open_loops', value: openLoops },
      { op: 'replace', path: '/metrics/closures_today', value: closuresToday },

      // Build permission
      { op: 'replace', path: '/build_allowed', value: buildAllowed },
    ];

    // Mode transition (only if changed)
    const modeChanged = currentMode !== newMode;
    if (modeChanged) {
      patches.push({ op: 'replace', path: '/mode', value: newMode });
      patches.push({ op: 'replace', path: '/last_mode_transition_at', value: timestamp });
      patches.push({ op: 'replace', path: '/last_mode_transition_reason', value: `Closure event: ratio=${closureRatio.toFixed(2)}` });
    }

    // Streak update (BUILD-only)
    if (streakUpdated) {
      patches.push({ op: 'replace', path: '/streak_days', value: currentStreakDays + 1 });
      patches.push({ op: 'replace', path: '/streak/last_increment_date', value: todayStr });
      if (closuresRegistry.stats.streak_days > (existing.state.best_streak as number || 0)) {
        patches.push({ op: 'replace', path: '/best_streak', value: closuresRegistry.stats.streak_days });
      }
    }

    const result = await createDelta(
      existing.entity,
      existing.state,
      patches,
      'closure_engine'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      closure: closureEntry,
      metrics: {
        closed_loops_total: currentClosedTotal + 1,
        closure_ratio: closureRatio,
        open_loops: openLoops,
        closures_today: closuresToday,
      },
      mode: newMode,
      mode_changed: modeChanged,
      build_allowed: buildAllowed,
      violations_reset: true,
      streak: {
        days: streakUpdated ? currentStreakDays + 1 : currentStreakDays,
        updated: streakUpdated,
        best: closuresRegistry.stats.best_streak,
        build_only: true,
      },
      physical_closure: loop_id ? 'attempted' : 'skipped',
    });
  } else {
    // No existing system_state — create genesis state
    const genesisState = {
      mode: newMode,
      build_allowed: buildAllowed,
      streak_days: streakUpdated ? 1 : 0,
      best_streak: streakUpdated ? 1 : 0,
      metrics: {
        closed_loops_total: 1,
        last_closure_at: timestamp,
        closure_ratio: closureRatio,
        open_loops: openLoops,
        closures_today: closuresToday,
      },
      enforcement: {
        violations_count: 0,
        violation_log: [],
        overrides_count: 0,
        override_log: [],
        closure_log: [closureEntry],
      },
      streak: {
        last_increment_date: streakUpdated ? todayStr : null,
      },
    };

    const result = await createEntity('system_state', genesisState as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    res.json({
      success: true,
      closure: closureEntry,
      metrics: {
        closed_loops_total: 1,
        closure_ratio: closureRatio,
        open_loops: openLoops,
        closures_today: closuresToday,
      },
      mode: newMode,
      mode_changed: true,
      build_allowed: buildAllowed,
      violations_reset: true,
      streak: {
        days: streakUpdated ? 1 : 0,
        updated: streakUpdated,
        best: streakUpdated ? 1 : 0,
        build_only: true,
      },
      physical_closure: loop_id ? 'attempted' : 'skipped',
    });
  }
});

// === WORK ADMISSION CONTROL (Phase 6A) ===

/**
 * Helper to get current system state for work admission checks.
 */
function getSystemStateForWork(): { mode: string; build_allowed: boolean; open_loops: number; closure_ratio: number } {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  if (entities.length > 0) {
    const state = entities[0].state;
    return {
      mode: (state.mode as string) || 'CLOSURE',
      build_allowed: (state.build_allowed as boolean) ?? false,
      open_loops: (state.metrics as Record<string, unknown>)?.open_loops as number || 0,
      closure_ratio: (state.metrics as Record<string, unknown>)?.closure_ratio as number || 0,
    };
  }
  return { mode: 'CLOSURE', build_allowed: false, open_loops: 0, closure_ratio: 0 };
}

/**
 * POST /api/work/request
 * Request permission to start a job.
 * Returns APPROVED, QUEUED, or DENIED.
 *
 * Body: {
 *   job_id?: string,
 *   type: "human" | "ai" | "system",
 *   title: string,
 *   agent?: string,
 *   weight?: number (1-10),
 *   depends_on?: string[],
 *   timeout_ms?: number,
 *   metadata?: object
 * }
 */
app.post('/api/work/request', (req, res) => {
  const { job_id, type, title, agent, weight, depends_on, timeout_ms, metadata } = req.body;

  if (!type || !title) {
    res.status(400).json({ error: 'type and title are required' });
    return;
  }

  if (!['human', 'ai', 'system'].includes(type)) {
    res.status(400).json({ error: 'type must be "human", "ai", or "system"' });
    return;
  }

  const systemState = getSystemStateForWork();

  const result = workController.request(
    { job_id, type, title, agent, weight, depends_on, timeout_ms, metadata },
    systemState
  );

  res.json(result);
});

/**
 * POST /api/work/complete
 * Report job completion.
 *
 * Body: {
 *   job_id: string,
 *   outcome: "completed" | "failed" | "abandoned",
 *   result?: object,
 *   error?: string,
 *   metrics?: { duration_ms?: number, tokens_used?: number, cost_usd?: number }
 * }
 */
app.post('/api/work/complete', (req, res) => {
  const { job_id, outcome, result: jobResult, error, metrics } = req.body;

  if (!job_id || !outcome) {
    res.status(400).json({ error: 'job_id and outcome are required' });
    return;
  }

  if (!['completed', 'failed', 'abandoned'].includes(outcome)) {
    res.status(400).json({ error: 'outcome must be "completed", "failed", or "abandoned"' });
    return;
  }

  const completeResult = workController.complete({ job_id, outcome, result: jobResult, error, metrics });

  if ('error' in completeResult) {
    res.status(completeResult.status).json({ error: completeResult.error });
    return;
  }

  res.json(completeResult);
});

/**
 * GET /api/work/status
 * Query current work state.
 */
app.get('/api/work/status', (req, res) => {
  const systemState = getSystemStateForWork();
  const status = workController.status(systemState);
  res.json(status);
});

/**
 * POST /api/work/cancel
 * Cancel a queued or active job.
 *
 * Body: { job_id: string, reason?: string }
 */
app.post('/api/work/cancel', (req, res) => {
  const { job_id, reason } = req.body;

  if (!job_id) {
    res.status(400).json({ error: 'job_id is required' });
    return;
  }

  const result = workController.cancel({ job_id, reason });

  if ('error' in result) {
    res.status(result.status).json({ error: result.error });
    return;
  }

  res.json(result);
});

/**
 * GET /api/work/history
 * Get completed jobs history.
 */
app.get('/api/work/history', (req, res) => {
  const ledger = workController.getLedger();
  res.json({
    completed: ledger.completed.slice(0, 20),
    stats: ledger.stats,
  });
});

// === TIMELINE (Phase 6C) ===

/**
 * GET /api/timeline
 * Query timeline events with optional filters.
 *
 * Query params:
 *   from: ISO timestamp (optional)
 *   to: ISO timestamp (optional)
 *   type: event type filter (optional)
 *   source: source filter (optional)
 *   limit: max events to return (default 100)
 */
app.get('/api/timeline', (req, res) => {
  const { from, to, type, source, limit } = req.query;

  const events = timeline.query({
    from: from as string | undefined,
    to: to as string | undefined,
    type: type as import('../core/timeline-logger').TimelineEventType | undefined,
    source: source as import('../core/timeline-logger').TimelineSource | undefined,
    limit: limit ? parseInt(limit as string, 10) : 100,
  });

  res.json({
    events,
    count: events.length,
    query: { from, to, type, source, limit: limit || 100 },
  });
});

/**
 * GET /api/timeline/stats
 * Get timeline statistics.
 */
app.get('/api/timeline/stats', (req, res) => {
  const stats = timeline.getStats();
  res.json(stats);
});

/**
 * GET /api/timeline/day/:date
 * Get all events for a specific day.
 *
 * Params:
 *   date: YYYY-MM-DD format
 */
app.get('/api/timeline/day/:date', (req, res) => {
  const { date } = req.params;
  const events = timeline.getDay(date);
  res.json({
    date,
    events,
    count: events.length,
  });
});

// === HEALTH ===

/**
 * GET /api/health
 * Simple health check endpoint.
 */
app.get('/api/health', (req, res) => {
  res.json({
    ok: true,
    ts: new Date().toISOString(),
    version: '1.0.0',
    service: 'delta-kernel',
  });
});

// === DAEMON ===

/**
 * GET /api/daemon/status
 * Returns current daemon state including job history.
 */
app.get('/api/daemon/status', (req, res) => {
  const status = daemon.getStatus();
  res.json({
    ok: true,
    ts: new Date().toISOString(),
    ...status,
  });
});

/**
 * POST /api/daemon/run
 * Manually trigger a daemon job.
 * Body: { job: "heartbeat" | "refresh" | "day_start" | "day_end" }
 */
app.post('/api/daemon/run', async (req, res) => {
  const { job } = req.body;

  const validJobs: JobName[] = ['heartbeat', 'refresh', 'day_start', 'day_end'];
  if (!job || !validJobs.includes(job)) {
    res.status(400).json({
      ok: false,
      error: `Invalid job. Must be one of: ${validJobs.join(', ')}`,
    });
    return;
  }

  try {
    const result = await daemon.runJob(job as JobName);
    res.json({
      ok: true,
      ts: new Date().toISOString(),
      job: result,
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: (error as Error).message,
    });
  }
});

// === STATS ===

app.get('/api/stats', (req, res) => {
  const stats = storage.getStats();
  res.json(stats);
});

// Start server
app.listen(PORT, () => {
  console.log(`Delta-State Fabric API running at http://localhost:${PORT}`);
  console.log(`Data directory: ${dataDir}`);
});
