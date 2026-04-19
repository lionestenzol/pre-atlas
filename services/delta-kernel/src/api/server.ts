/**
 * Delta-State Fabric — API Server
 *
 * Shared backend for CLI and web app.
 * Stores data in ~/.delta-fabric/
 */

import express from 'express';
import cors from 'cors';
import { Storage } from '../cli/sqlite-storage';
import { createEntity, createDelta, now } from '../core/delta';
import { getDaemon, JobName } from '../governance/governance_daemon';
import { WorkController } from '../core/work-controller';
import { getTimelineLogger } from '../core/timeline-logger.js';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';
import { spawn as spawnChild } from 'child_process';
import { emitEvent } from '../core/event-emitter.js';
import { AegisClient } from '../clients/aegis-client.js';
import { DirectiveEmitter, DirectiveValidationError } from '../atlas/directive.js';
import {
  ingestSignal,
  listSignals,
  resolveSignal,
  SignalValidationError,
} from '../atlas/signals-store.js';

// ES Module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3001;

// Storage
const dataDir = process.env.DELTA_DATA_DIR || path.join(os.homedir(), '.delta-fabric');
const storage = new Storage({ dataDir });

// Repo root (for daemon and cross-service file reads)
// From compiled dist/api/server.js: go up 4 levels to reach Pre Atlas root
// dist/api → dist → delta-kernel → services → Pre Atlas
const repoRoot = process.env.DELTA_REPO_ROOT
  || (process.env.DELTA_DATA_DIR ? path.resolve(process.env.DELTA_DATA_DIR, '..') : path.resolve(__dirname, '../../../..'));

// Cognitive sensor directory (configurable for standalone operation)
const cognitiveSensorDir = process.env.COGNITIVE_SENSOR_DIR
  || path.join(repoRoot, 'services', 'cognitive-sensor');

// Initialize and start governance daemon
const daemon = getDaemon(storage, repoRoot);
daemon.start();

// Initialize work controller
const workController = new WorkController(repoRoot);

// Initialize timeline logger
const timeline = getTimelineLogger(repoRoot);

// === SECURITY ===

// CORS: restrict to known local origins
app.use(cors({
  origin: [
    'http://localhost:8765', 'http://127.0.0.1:8765',
    'http://localhost:3001', 'http://127.0.0.1:3001',
    'http://localhost:3000', 'http://127.0.0.1:3000', // Mosaic Dashboard
    'http://localhost:5500', 'http://127.0.0.1:5500', // Live Server
    'http://localhost:5501', 'http://127.0.0.1:5501', // Live Server alt
    'http://localhost:8888', 'http://127.0.0.1:8888', // Atlas Shell
    'http://localhost:8889', 'http://127.0.0.1:8889', // CycleBoard
    'http://localhost:3008', 'http://127.0.0.1:3008', // UASC Executor
    'http://localhost:3006', 'http://127.0.0.1:3006', // inPACT
    'null', // file:// protocol
  ],
}));
app.use(express.json());

// Load API key from .aegis-tenant-key
const keyPath = path.join(repoRoot, '.aegis-tenant-key');
let API_KEY: string | null = null;
try {
  API_KEY = fs.readFileSync(keyPath, 'utf-8').trim();
  console.log('API key loaded from .aegis-tenant-key');
} catch {
  console.warn('WARNING: No .aegis-tenant-key found — running without auth (dev mode)');
}

// Initialize Aegis policy client (graceful degradation if unreachable)
const aegisClient = new AegisClient('http://localhost:3002', API_KEY ?? '', 5000);

// Auth middleware: require Bearer token on /api/* (except health and token endpoints)
app.use('/api', (req, res, next) => {
  if (!API_KEY) { next(); return; } // dev mode: no key file = no auth
  if (req.path === '/health' || req.path === '/services/health' || req.path === '/auth/token') { next(); return; }

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Missing or invalid API key' });
    return;
  }
  const token = authHeader.slice(7);
  if (token !== API_KEY) {
    res.status(401).json({ error: 'Missing or invalid API key' });
    return;
  }
  next();
});

// Token endpoint: browser clients fetch the key once (localhost-only, CORS-restricted)
app.get('/api/auth/token', (req, res) => {
  if (!API_KEY) {
    res.json({ ok: true, token: null });
    return;
  }
  res.json({ ok: true, token: API_KEY });
});

// Serve control panel UI
app.use('/control', express.static(path.join(__dirname, '../ui')));

const realtimeClients = new Set<express.Response>();
let lastUnifiedStateSnapshot: string | null = null;

const sendSseEvent = (res: express.Response, event: string, payload: unknown) => {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
};

const broadcastSseEvent = (event: string, payload: unknown) => {
  for (const client of realtimeClients) {
    sendSseEvent(client, event, payload);
  }
};

// === UNIFIED STATE (must be before /api/state to avoid route conflict) ===

/**
 * GET /api/state/unified
 * Single truth payload merging Delta authoritative state + cognitive snapshots.
 * Gracefully handles missing files.
 */
const buildUnifiedState = () => {
  const errors: string[] = [];

  // A) Load Delta authoritative state
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  const deltaState = entities.length > 0 ? entities[0].state : null;

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
  const cognitiveStatePath = path.join(cognitiveSensorDir, 'cognitive_state.json');
  const loopsLatestPath = path.join(cognitiveSensorDir, 'loops_latest.json');
  const todayPath = path.join(repoRoot, 'data/projections/today.json');
  const closuresPath = path.join(cognitiveSensorDir, 'closures.json');

  const cognitiveState = readJsonFile(cognitiveStatePath, 'cognitive_state.json') as Record<string, unknown> | null;
  const loopsLatest = readJsonFile(loopsLatestPath, 'loops_latest.json') as unknown[] | null;
  const today = readJsonFile(todayPath, 'today.json') as Record<string, unknown> | null;
  const closuresRegistry = readJsonFile(closuresPath, 'closures.json') as { closures: unknown[]; stats: Record<string, unknown> } | null;

  // D) Derive unified values
  //
  // PRIORITY CASCADE (documented for Phase 0 audit):
  //   Mode:          today.json > delta state > default ('RECOVER')
  //   Risk:          today.json > delta state > default ('MEDIUM')
  //   Open loops:    cognitive_state > today.json > delta state > default (0)
  //   Closure ratio: cognitive_state > today.json > delta state > default (0)
  //   Primary order: today.json > delta state > default
  //   Build allowed: today.json > delta state > computed from mode
  //
  // Why this order: cognitive_state.json is refreshed daily by the pipeline
  // and contains the most granular loop/closure data. today.json is the daily
  // directive (mode routing output). delta state is the persistent store.
  // If files are missing or stale, later sources provide a safe fallback.
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
  // Cognitive files store ratio as percentage (e.g. 72.0); normalize to decimal (0.0-1.0)
  const rawRatio = (closureData?.ratio as number)
    ?? (todayCognitive?.closure as Record<string, unknown>)?.ratio as number
    ?? (deltaState?.closure_ratio as number)
    ?? 0;
  const closureRatio = rawRatio > 1 ? rawRatio / 100 : rawRatio;

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

  return {
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
  };
};

const emitUnifiedStateIfChanged = () => {
  const unifiedState = buildUnifiedState();
  const snapshot = JSON.stringify(unifiedState);
  if (snapshot === lastUnifiedStateSnapshot) {
    return;
  }
  lastUnifiedStateSnapshot = snapshot;
  broadcastSseEvent('unified_state', {
    ok: true,
    ts: new Date().toISOString(),
    ...unifiedState,
  });
};

const emitDeltaCreated = (delta: unknown) => {
  broadcastSseEvent('delta_created', {
    ok: true,
    ts: new Date().toISOString(),
    delta,
  });
};

app.get('/api/state/unified', (req, res) => {
  const unifiedState = buildUnifiedState();
  res.json({
    ok: true,
    ts: new Date().toISOString(),
    ...unifiedState,
  });
});

app.get('/api/state/unified/stream', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });

  res.write('retry: 10000\n\n');
  realtimeClients.add(res);

  const initialState = buildUnifiedState();
  sendSseEvent(res, 'unified_state', {
    ok: true,
    ts: new Date().toISOString(),
    ...initialState,
  });

  req.on('close', () => {
    realtimeClients.delete(res);
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
  const currentTime = now();

  const stateData: SystemStateData = {
    mode: newState.mode as SystemStateData['mode'],
    signals: {
      sleep_hours: newState.sleepHours ?? 6,
      open_loops: newState.openLoops ?? 0,
      assets_shipped: 0,
      deep_work_blocks: 0,
      money_delta: 0,
    },
    // Preserve flat fields for backward compat with existing readers
    sleep_hours: newState.sleepHours,
    open_loops: newState.openLoops,
    leverage_balance: newState.leverageBalance,
    streak_days: newState.streakDays,
  };

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length > 0) {
    // Update existing
    const existing = entities[0];
    const patches = Object.entries(stateData).map(([key, value]) => ({
      op: 'replace' as const,
      path: `/${key}`,
      value,
    }));
    if ((existing.state.mode as string | undefined) !== stateData.mode) {
      patches.push({ op: 'replace', path: '/mode_since', value: currentTime });
    }
    const result = await createDelta(
      existing.entity,
      existing.state,
      patches,
      'user'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  } else {
    // Create new
    const result = await createEntity('system_state', {
      ...stateData,
      mode_since: currentTime,
    });
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
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

  const taskData: TaskData = {
    title_template: title,
    title_params: {},
    status: 'OPEN',
    priority: priority as Exclude<Priority, 'CRITICAL'>,
    due_at: null,
    linked_thread: null,
  };

  const result = await createEntity('task', taskData);
  storage.saveEntity(result.entity, result.state);
  storage.appendDelta(result.delta);
  emitDeltaCreated(result.delta);
  emitUnifiedStateIfChanged();

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

      // Feedback loop: task completion triggers closure pipeline
      if (updates.status === 'DONE') {
        processClosureEvent({
          title: (state.title as string) || 'Task completed',
          outcome: 'closed',
        }).catch(e => console.error('[task_complete] Closure feedback failed:', e));
      }

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
const _processedRunIds = new Set<string>();

app.post('/api/ingest/cognitive', async (req, res) => {
  const projection = req.body;

  // Idempotency: skip duplicate run_ids
  if (projection.run_id) {
    if (_processedRunIds.has(projection.run_id)) {
      res.json({ success: true, deduplicated: true, run_id: projection.run_id });
      return;
    }
    _processedRunIds.add(projection.run_id);
    // Keep set bounded (last 1000 run_ids)
    if (_processedRunIds.size > 1000) {
      const first = _processedRunIds.values().next().value;
      if (first !== undefined) _processedRunIds.delete(first);
    }
  }

  // Validate required fields
  if (!projection.cognitive || !projection.directive) {
    res.status(400).json({ error: 'Invalid projection: missing cognitive or directive' });
    return;
  }

  const { cognitive, directive } = projection;
  const ingestTime = now();

  // Schema version validation
  const PYTHON_VALID_MODES = ['CLOSURE', 'MAINTENANCE', 'BUILD'];
  if (directive.mode_source === 'cognitive-sensor' && !PYTHON_VALID_MODES.includes(directive.mode)) {
    console.warn(`[Ingest] Warning: cognitive-sensor sent mode '${directive.mode}' which is outside its valid set (${PYTHON_VALID_MODES.join(', ')})`);
  }
  if (directive.schema_version) {
    console.log(`[Ingest] Received payload schema_version=${directive.schema_version} from ${directive.mode_source || 'unknown'}`);
  }

  // Map to system_state format (partial - uses any cast for flexibility)
  const stateData: Record<string, unknown> = {
    mode: directive.mode,
    open_loops: cognitive.closure?.open ?? directive.open_loop_count ?? 0,
    closure_ratio: cognitive.closure?.ratio ?? directive.closure_ratio ?? 0,
    risk: directive.risk,
    build_allowed: directive.build_allowed,
    primary_action: directive.primary_action,
    last_ingest: now(),
    last_run_id: projection.run_id || null,
  };

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');

  if (entities.length > 0) {
    // Update existing
    const existing = entities[0];
    const patches = Object.entries(stateData).map(([key, value]) => ({
      op: 'replace' as const,
      path: `/${key}`,
      value,
    }));
    if ((existing.state.mode as string | undefined) !== directive.mode) {
      patches.push({ op: 'replace', path: '/mode_since', value: ingestTime });
    }
    const result = await createDelta(
      existing.entity,
      existing.state,
      patches,
      'cognitive-sensor'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  } else {
    // Create new (cast since cognitive state differs from full SystemStateData)
    const result = await createEntity('system_state', {
      ...stateData,
      mode_since: ingestTime,
    } as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  }

  res.json({
    success: true,
    mode: stateData.mode,
    open_loops: stateData.open_loops,
    run_id: projection.run_id || null,
  });
});

// === DAILY BRIEF ===

/**
 * GET /api/daily-brief
 * Returns structured daily brief data for the cockpit dashboard.
 * Reads governance_state.json, daily_payload.json, and daily_brief.md.
 */
app.get('/api/daily-brief', (_req, res) => {
  const CS = path.resolve(__dirname, '..', '..', '..', 'cognitive-sensor');

  const readJson = (file: string) => {
    try { return JSON.parse(fs.readFileSync(path.join(CS, file), 'utf8')); }
    catch { return null; }
  };
  const readText = (file: string) => {
    try { return fs.readFileSync(path.join(CS, file), 'utf8'); }
    catch { return null; }
  };

  const governance = readJson('governance_state.json');
  const payload = readJson('daily_payload.json');
  const cogState = readJson('cognitive_state.json');
  const briefMd = readText('daily_brief.md');

  // Extract leverage moves from daily_brief.md
  const moves: string[] = [];
  if (briefMd) {
    const movesMatch = briefMd.match(/## Top Moves Today[\s\S]*?(?=##|$)/);
    if (movesMatch) {
      const lines = movesMatch[0].split('\n').filter((l: string) => /^\d+\./.test(l.trim()));
      for (const l of lines) moves.push(l.replace(/^\d+\.\s*/, '').trim());
    }
  }

  // Extract decisions from daily_brief.md
  const decisions: string[] = [];
  if (briefMd) {
    const decMatch = briefMd.match(/## Decisions Required[\s\S]*?(?=##|$)/);
    if (decMatch) {
      const lines = decMatch[0].split('\n').filter((l: string) => /^\*\*\d+\./.test(l.trim()));
      for (const l of lines) decisions.push(l.replace(/^\*\*\d+\.\s*/, '').replace(/\*\*/g, '').trim());
    }
  }

  res.json({
    ok: true,
    ts: new Date().toISOString(),
    mode: payload?.mode || governance?.mode || 'RECOVER',
    risk: payload?.risk || governance?.risk || 'MEDIUM',
    build_allowed: payload?.build_allowed ?? governance?.build_allowed ?? false,
    primary_action: payload?.primary_action || governance?.primary_action || '',
    closure: {
      ratio: cogState?.closure?.ratio ?? payload?.closure_ratio ?? 0,
      open: cogState?.closure?.open ?? payload?.open_loop_count ?? 0,
    },
    leverage_moves: moves.length > 0 ? moves : [
      governance?.leverage_moves?.[0] || 'No moves computed — run daily refresh',
    ],
    decisions,
    lanes: governance?.active_lanes || governance?.lane_status || [],
    directive: payload?.primary_action || 'Run atlas_cli.py daily to generate brief',
    brief_generated: governance?.generated_at || payload?.generated_at || null,
    brief_raw: briefMd,
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  } else {
    const result = await createEntity('system_state', acknowledgeData as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  } else {
    const result = await createEntity('system_state', { archived_loops: [archiveEntry] } as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  }

  res.json({
    success: true,
    archived: archiveEntry,
  });
});

/**
 * POST /api/law/refresh
 * Request a cognitive sensor refresh. Records timestamp and spawns refresh.py.
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  } else {
    const result = await createEntity('system_state', refreshData as any);
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();
  }

  // Spawn refresh.py in background (fire-and-forget with logging)
  const refreshPath = path.join(cognitiveSensorDir, 'refresh.py');
  if (fs.existsSync(refreshPath)) {
    const proc = spawnChild('python', [refreshPath], {
      cwd: cognitiveSensorDir,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    proc.stdout?.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d: Buffer) => { stderr += d.toString(); });

    const timeout = setTimeout(() => { proc.kill(); }, 120_000);
    proc.on('close', (code: number | null) => {
      clearTimeout(timeout);
      if (code === 0) {
        timeline.emit('REFRESH_COMPLETED', 'api', { triggered_by: 'law/refresh', output: stdout.slice(-200) });
      } else {
        timeline.emit('REFRESH_FAILED', 'api', { code, stderr: stderr.slice(-200) });
      }
    });
  }

  res.json({
    success: true,
    refresh_requested_at: refreshData.last_refresh_requested_at,
    refresh_spawned: fs.existsSync(refreshPath),
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

    res.json({
      success: true,
      overrides_count: 1,
      override_logged: true,
    });
  }
});

/**
 * Internal closure processor — reusable by close_loop API and task completion.
 * Fire-and-forget: errors are logged but don't propagate.
 */
async function processClosureEvent(closureInput: { loop_id?: string; title?: string; outcome: 'closed' | 'archived' }): Promise<{ success: boolean; mode?: string; mode_changed?: boolean; closureRatio?: number; closuresToday?: number; closedTotal?: number; openLoops?: number; buildAllowed?: boolean; streakDays?: number; streakUpdated?: boolean; bestStreak?: number }> {
  const { loop_id, title, outcome } = closureInput;
  const timestamp = now();
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayStartTs = todayStart.getTime();
  const todayStr = todayStart.toISOString().split('T')[0];

  // Load closures registry
  const closuresPath = path.join(cognitiveSensorDir, 'closures.json');
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

  // Idempotency check
  if (loop_id) {
    const alreadyClosed = closuresRegistry.closures.some(c => c.loop_id === loop_id);
    if (alreadyClosed) return { success: false };
  }

  // Build closure entry
  const closureEntry = { ts: timestamp, loop_id: loop_id || null, title: title || null, outcome };
  closuresRegistry.closures.push(closureEntry);
  closuresRegistry.stats.total_closures += 1;
  closuresRegistry.stats.last_closure_at = timestamp;
  const closuresToday = closuresRegistry.closures.filter(c => c.ts >= todayStartTs).length;
  closuresRegistry.stats.closures_today = closuresToday;

  // Read cognitive state for ratio
  const cognitiveStatePath = path.join(cognitiveSensorDir, 'cognitive_state.json');
  let openLoops = 0;
  try {
    if (fs.existsSync(cognitiveStatePath)) {
      const cogState = JSON.parse(fs.readFileSync(cognitiveStatePath, 'utf-8'));
      openLoops = cogState.closure?.open ?? 0;
    }
  } catch { /* default */ }

  const closedLoops = closuresRegistry.stats.total_closures;
  const totalLoops = openLoops + closedLoops;
  const closureRatio = totalLoops > 0 ? closedLoops / totalLoops : 1;

  // Mode transition rules
  let newMode: string;
  let buildAllowed: boolean;
  if (closureRatio >= 0.8) { newMode = 'SCALE'; buildAllowed = true; }
  else if (closureRatio >= 0.6) { newMode = 'BUILD'; buildAllowed = true; }
  else if (closureRatio >= 0.4) { newMode = 'MAINTENANCE'; buildAllowed = false; }
  else { newMode = 'CLOSURE'; buildAllowed = false; }

  // Streak increment (BUILD-only)
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

  // Write closures registry
  const closuresDir = path.dirname(closuresPath);
  if (!fs.existsSync(closuresDir)) fs.mkdirSync(closuresDir, { recursive: true });
  fs.writeFileSync(closuresPath, JSON.stringify(closuresRegistry, null, 2));

  // Physical loop closure hooks
  if (loop_id) {
    const loopsLatestPath = path.join(cognitiveSensorDir, 'loops_latest.json');
    const loopsClosedPath = path.join(cognitiveSensorDir, 'loops_closed.json');
    try {
      if (fs.existsSync(loopsLatestPath)) {
        const loopsLatest = JSON.parse(fs.readFileSync(loopsLatestPath, 'utf-8')) as Array<{ id?: string; loop_id?: string }>;
        const filtered = loopsLatest.filter(l => l.id !== loop_id && l.loop_id !== loop_id);
        if (filtered.length !== loopsLatest.length) {
          fs.writeFileSync(loopsLatestPath, JSON.stringify(filtered, null, 2));
        }
      }
      let loopsClosed: Array<{ loop_id: string; title: string | null; closed_at: number; outcome: string }> = [];
      if (fs.existsSync(loopsClosedPath)) loopsClosed = JSON.parse(fs.readFileSync(loopsClosedPath, 'utf-8'));
      loopsClosed.push({ loop_id, title: title || null, closed_at: timestamp, outcome });
      fs.writeFileSync(loopsClosedPath, JSON.stringify(loopsClosed, null, 2));
    } catch (e) {
      console.error('[processClosureEvent] Physical loop removal failed:', (e as Error).message);
    }
  }

  // Update delta state
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('system_state');
  const currentStreakDays = entities.length > 0 ? (entities[0].state.streak_days as number) || 0 : 0;

  if (entities.length > 0) {
    const existing = entities[0];
    const currentMode = (existing.state.mode as string) || 'CLOSURE';
    const currentMetrics = (existing.state.metrics as Record<string, unknown>) || {};
    const currentEnforcement = (existing.state.enforcement as Record<string, unknown>) || {};
    const currentClosureLog = (currentEnforcement.closure_log as unknown[]) || [];
    const currentClosedTotal = (currentMetrics.closed_loops_total as number) || 0;

    const patches: Array<{ op: 'replace'; path: string; value: unknown }> = [
      { op: 'replace', path: '/enforcement/violations_count', value: 0 },
      { op: 'replace', path: '/enforcement/closure_log', value: [...currentClosureLog, closureEntry] },
      { op: 'replace', path: '/metrics/closed_loops_total', value: currentClosedTotal + 1 },
      { op: 'replace', path: '/metrics/last_closure_at', value: timestamp },
      { op: 'replace', path: '/metrics/closure_ratio', value: closureRatio },
      { op: 'replace', path: '/metrics/open_loops', value: openLoops },
      { op: 'replace', path: '/metrics/closures_today', value: closuresToday },
      { op: 'replace', path: '/build_allowed', value: buildAllowed },
    ];

    const modeChanged = currentMode !== newMode;
    if (modeChanged) {
      patches.push({ op: 'replace', path: '/mode', value: newMode });
      patches.push({ op: 'replace', path: '/last_mode_transition_at', value: timestamp });
      patches.push({ op: 'replace', path: '/last_mode_transition_reason', value: `Closure event: ratio=${closureRatio.toFixed(2)}` });
    }

    if (streakUpdated) {
      patches.push({ op: 'replace', path: '/streak_days', value: currentStreakDays + 1 });
      patches.push({ op: 'replace', path: '/streak/last_increment_date', value: todayStr });
      if (closuresRegistry.stats.streak_days > (existing.state.best_streak as number || 0)) {
        patches.push({ op: 'replace', path: '/best_streak', value: closuresRegistry.stats.streak_days });
      }
    }

    const result = await createDelta(existing.entity, existing.state, patches, 'closure_engine');
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);

    timeline.emit('CLOSURE_PROCESSED', 'closure_engine', {
      loop_id: loop_id || null,
      title: title || null,
      outcome,
      mode: newMode,
      mode_changed: modeChanged,
      closure_ratio: closureRatio,
    });

    return {
      success: true,
      mode: newMode,
      mode_changed: modeChanged,
      closureRatio,
      closuresToday,
      closedTotal: currentClosedTotal + 1,
      openLoops,
      buildAllowed,
      streakDays: streakUpdated ? currentStreakDays + 1 : currentStreakDays,
      streakUpdated,
      bestStreak: closuresRegistry.stats.best_streak,
    };
  }

  return { success: true, mode: newMode, mode_changed: false };
}

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
  const closuresPath = path.join(cognitiveSensorDir, 'closures.json');
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
  const cognitiveStatePath = path.join(cognitiveSensorDir, 'cognitive_state.json');
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
    const loopsLatestPath = path.join(cognitiveSensorDir, 'loops_latest.json');
    const loopsClosedPath = path.join(cognitiveSensorDir, 'loops_closed.json');

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
      patches.push({ op: 'replace', path: '/mode_since', value: timestamp });
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

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

    // Emit loop.closed to NATS event bus for real-time UI push
    emitEvent('loop.closed', {
      loopId: loop_id || null,
      loopTitle: title || null,
      outcome,
      closedAt: new Date(timestamp).toISOString(),
      newMode,
      modeChanged,
      closureRatio,
    }).catch(() => {}); // Best-effort
  } else {
    // No existing system_state — create genesis state
    const genesisState = {
      mode: newMode,
      mode_since: timestamp,
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
    emitDeltaCreated(result.delta);
    emitUnifiedStateIfChanged();

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
app.post('/api/work/request', async (req, res) => {
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

  // Aegis policy gate — only for APPROVED jobs, graceful degradation on failure
  if (result.status === 'APPROVED' && result.job_id) {
    try {
      const aegis = await aegisClient.submitAction(
        agent || 'unknown',
        'work_request',
        { title, type, agent, mode: systemState.mode },
      );
      if (aegis.decision === 'REQUIRE_HUMAN') {
        // Low-risk actions auto-approve: system work, morning/wrap routines, stale cleanup
        const lowRiskPatterns = ['morning', 'wrap', 'close-stale', 'checkpoint', 'refresh', 'process-inbox'];
        const isLowRisk = type === 'system' || lowRiskPatterns.some(p => (title || '').toLowerCase().includes(p));
        if (!isLowRisk) {
          workController.cancel({ job_id: result.job_id, reason: 'Aegis: awaiting human approval' });
          res.json({ status: 'QUEUED', job_id: result.job_id, position: 0, queue_depth: 0, reason: 'Awaiting human approval (Aegis policy)', blocked_by: [], estimated_wait_ms: 0 });
          return;
        }
        // Low-risk: auto-approve, proceed as APPROVED
      }
      if (aegis.decision === 'DENY') {
        workController.cancel({ job_id: result.job_id, reason: aegis.reason || 'Denied by Aegis policy' });
        res.json({ status: 'DENIED', reason: aegis.reason || 'Denied by Aegis policy' });
        return;
      }
    } catch {
      // Aegis unreachable — graceful degradation, proceed with APPROVED
    }
  }

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
 * POST /api/work/claim
 * Atomically claim the next approved executable task for autonomous execution.
 *
 * Body: { executor_id: string }
 */
app.post('/api/work/claim', (req, res) => {
  const { executor_id } = req.body;

  if (!executor_id || typeof executor_id !== 'string') {
    res.status(400).json({ error: 'executor_id is required' });
    return;
  }

  const claim = workController.claimNextExecutable(executor_id);
  res.json(claim);
});

/**
 * POST /api/work/heartbeat
 * Extend the claim on an active executable task.
 *
 * Body: { job_id: string, executor_id: string, extension_ms?: number }
 */
app.post('/api/work/heartbeat', (req, res) => {
  const { job_id, executor_id, extension_ms } = req.body;

  if (!job_id || typeof job_id !== 'string' || !executor_id || typeof executor_id !== 'string') {
    res.status(400).json({ error: 'job_id and executor_id are required' });
    return;
  }

  if (extension_ms !== undefined && (typeof extension_ms !== 'number' || extension_ms <= 0)) {
    res.status(400).json({ error: 'extension_ms must be a positive number when provided' });
    return;
  }

  const result = workController.extendClaim(job_id, executor_id, extension_ms);
  if (!result.extended) {
    res.status(404).json({ error: 'Job not found or executor mismatch' });
    return;
  }

  res.json(result);
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

/**
 * GET /api/work/metrics
 * Lightweight claim/execution observability snapshot.
 */
app.get('/api/work/metrics', (_req, res) => {
  res.json({
    claims: workController.getClaimMetrics(),
  });
});

// === SIGNALS (Phase 3C of doctrine/04_BUILD_PLAN.md) ===
// Accepts Signal.v1 payloads from any layer, exposes them for InPACT.

app.post('/api/signals/ingest', (req, res) => {
  try {
    const signal = ingestSignal(repoRoot, req.body);
    res.status(202).json({ ok: true, signal_id: signal.id });
  } catch (error: unknown) {
    if (error instanceof SignalValidationError) {
      res.status(400).json({ ok: false, error: error.message, details: error.details });
      return;
    }
    const message = error instanceof Error ? error.message : 'Unknown error';
    res.status(500).json({ ok: false, error: message });
  }
});

app.get('/api/signals', (req, res) => {
  const since = typeof req.query.since === 'string' ? req.query.since : undefined;
  res.json({ ok: true, signals: listSignals(since) });
});

app.post('/api/signals/:id/resolve', (req, res) => {
  const signalId = req.params.id;
  const actionId = typeof req.body?.action_id === 'string' ? req.body.action_id : '';
  if (!actionId) {
    res.status(400).json({ ok: false, error: 'action_id required in body' });
    return;
  }
  const resolution = resolveSignal(signalId, actionId);
  if (!resolution) {
    res.status(404).json({ ok: false, error: `Signal ${signalId} not found` });
    return;
  }
  res.json({ ok: true, resolution });
});

// === ATLAS (Phase 3A of doctrine/04_BUILD_PLAN.md) ===

/**
 * GET /api/atlas/next-directive
 * Emit the next Directive.v1 for Ghost Executor (Cortex).
 * - 200 + { ok, directive } on success
 * - 204 if no active/queued job
 * - 500 + { ok:false, error, details } on schema validation failure
 */
app.get('/api/atlas/next-directive', (_req, res) => {
  try {
    const unifiedState = buildUnifiedState();
    const snapshot = {
      delta_state: (unifiedState.delta?.system_state ?? undefined) as Record<string, unknown> | undefined,
      cognitive_state: (unifiedState.cognitive?.cognitive_state ?? undefined) as Record<string, unknown> | undefined,
      work_ledger: workController.getLedger(),
    };
    const directive = new DirectiveEmitter(repoRoot).emit(snapshot);
    if (!directive) {
      res.status(204).end();
      return;
    }
    res.json({ ok: true, directive });
  } catch (error: unknown) {
    if (error instanceof DirectiveValidationError) {
      res.status(500).json({ ok: false, error: error.message, details: error.details });
      return;
    }
    const message = error instanceof Error ? error.message : 'Unknown error';
    res.status(500).json({ ok: false, error: message });
  }
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
    type: type as any,
    source: source as any,
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

/**
 * POST /api/timeline
 * Emit a timeline event from an external service (e.g., Cortex).
 * Body: { type: string, source?: string, data?: object }
 */
app.post('/api/timeline', (req, res) => {
  const { type, source = 'cortex', data } = req.body;

  if (!type) {
    res.status(400).json({ error: 'type required' });
    return;
  }

  const event = timeline.emit(type as any, source as any, data);
  res.json({ success: true, event_id: event.id, ts: event.ts });
});

/**
 * POST /api/tasks/status
 * Update a task's status by task_id. Used by Cortex execution layer.
 * Body: { task_id: string, status: string, metadata?: object }
 */
app.post('/api/tasks/status', (req, res) => {
  const { task_id, status, metadata } = req.body;

  if (!task_id || !status) {
    res.status(400).json({ error: 'task_id and status required' });
    return;
  }

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('task');
  let found = false;

  for (const e of entities) {
    if (e.entity.entity_id === task_id) {
      const state = e.state as Record<string, unknown>;
      state.status = status;
      if (metadata) {
        state.cortex_metadata = metadata;
      }
      if (status === 'DONE' || status === 'completed') {
        state.closed_at = now();
      }
      storage.saveEntity(e.entity, state);
      found = true;

      // Emit timeline event for tracking
      timeline.emit(
        status === 'completed' ? 'CORTEX_TASK_COMPLETED' as any :
        status === 'failed' || status === 'dead' ? 'CORTEX_TASK_FAILED' as any :
        'AUTO_EXECUTED',
        'cortex' as any,
        { task_id, status, ...metadata }
      );
      break;
    }
  }

  if (!found) {
    // Task doesn't exist in delta yet — create it so Cortex can track state
    const taskData: TaskData = {
      title_template: `cortex:${task_id}`,
      title_params: {},
      status: status === 'completed' ? 'DONE' : 'OPEN',
      priority: 'NORMAL',
      due_at: null,
      linked_thread: null,
    };

    createEntity('task', taskData).then(result => {
      storage.saveEntity(result.entity, result.state);
      storage.appendDelta(result.delta);
    }).catch(err => {
      console.error('[tasks/status] Auto-create failed:', err);
    });
  }

  res.json({ success: true, task_id, status, created: !found });
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

app.get('/api/services/health', async (_req, res) => {
  const results: Record<string, { status: string; data?: any }> = {};

  // Delta is always up if this endpoint responds.
  results.delta = { status: 'up', data: { service: 'delta-kernel' } };

  // Check UASC
  try {
    const uascRes = await fetch('http://localhost:3008/health', { signal: AbortSignal.timeout(3000) });
    if (uascRes.ok) {
      results.uasc = { status: 'up', data: await uascRes.json() };
    } else {
      results.uasc = { status: 'down' };
    }
  } catch {
    results.uasc = { status: 'down' };
  }

  // Check Cortex
  try {
    const cortexRes = await fetch('http://localhost:3009/health', { signal: AbortSignal.timeout(3000) });
    if (cortexRes.ok) {
      results.cortex = { status: 'up', data: await cortexRes.json() };
    } else {
      results.cortex = { status: 'down' };
    }
  } catch {
    results.cortex = { status: 'down' };
  }

  res.json(results);
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

// === GOVERNANCE CONFIG ===

app.get('/api/governance/config', (req, res) => {
  const configPath = path.resolve(cognitiveSensorDir, 'governance_config.json');
  try {
    const raw = fs.readFileSync(configPath, 'utf-8');
    res.json(JSON.parse(raw));
  } catch (err) {
    res.status(404).json({ error: 'governance_config.json not found. Run refresh pipeline first.' });
  }
});

// === IDEA REGISTRY ===

app.get('/api/ideas', (req, res) => {
  const ideasPath = path.resolve(cognitiveSensorDir, 'idea_registry.json');
  try {
    const raw = fs.readFileSync(ideasPath, 'utf-8');
    res.json(JSON.parse(raw));
  } catch (err) {
    res.status(404).json({ error: 'idea_registry.json not found. Run agent pipeline first.' });
  }
});

// === PREPARATION ENGINE OUTPUT ===

app.get('/api/preparation', (req, res) => {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('preparation_result');
  if (entities.length === 0) {
    res.json({
      ok: true,
      data: null,
      message: 'No preparation results yet. Daemon runs every 5 minutes.',
    });
    return;
  }
  res.json({ ok: true, data: entities[0].state });
});

// === NOTIFICATIONS (auto-execution audit trail) ===

app.get('/api/notifications', (req, res) => {
  const since = req.query.since as string || undefined;
  const typeFilter = req.query.types as string || undefined;

  const events = timeline.query({
    from: since ? new Date(parseInt(since)).toISOString() : undefined,
    limit: 50,
  });

  const filtered = typeFilter
    ? events.filter((e: any) => typeFilter.split(',').includes(e.type))
    : events;

  res.json({ ok: true, events: filtered });
});

// === CYCLEBOARD PERSISTENCE ===

app.get('/api/cycleboard', (req, res) => {
  const entities = storage.loadEntitiesByType<Record<string, unknown>>('cycle_board');
  if (entities.length === 0) {
    res.json({ ok: true, data: null });
    return;
  }
  res.json({ ok: true, data: entities[0].state });
});

app.put('/api/cycleboard', async (req, res) => {
  const newState = req.body;
  if (!newState || typeof newState !== 'object') {
    res.status(400).json({ ok: false, error: 'Request body must be a JSON object' });
    return;
  }

  const entities = storage.loadEntitiesByType<Record<string, unknown>>('cycle_board');

  if (entities.length > 0) {
    const existing = entities[0];
    const result = await createDelta(
      existing.entity,
      existing.state,
      [{ op: 'replace' as const, path: '/data', value: newState }],
      'cycleboard'
    );
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  } else {
    const result = await createEntity('cycle_board', { data: newState });
    storage.saveEntity(result.entity, result.state);
    storage.appendDelta(result.delta);
  }

  res.json({ ok: true });
});

// === PENDING ACTIONS + EXECUTOR BRIDGE ===

import { bridgeAction, checkExecutorHealth, getTokenForAction } from '../core/executor-bridge.js';
import type { PendingActionData, ActionType, PendingActionStatus, SystemStateData, TaskData, Priority } from '../core/types-core';

const PENDING_ACTION_TIMEOUT_MS = 30_000; // 30 seconds

// List pending actions
app.get('/api/actions/pending', (req, res) => {
  const entities = storage.loadEntitiesByType<PendingActionData>('pending_action');
  const pending = entities
    .filter(e => (e.state as PendingActionData).status === 'PENDING')
    .map(e => ({
      id: e.entity.entity_id,
      action_type: (e.state as PendingActionData).action_type,
      target_entity_id: (e.state as PendingActionData).target_entity_id,
      status: (e.state as PendingActionData).status,
      created_at: (e.state as PendingActionData).created_at,
      expires_at: (e.state as PendingActionData).expires_at,
      token: getTokenForAction((e.state as PendingActionData).action_type),
    }));

  res.json({ pending_actions: pending });
});

// Create a pending action
app.post('/api/actions/pending', async (req, res) => {
  const { action_type, target_entity_id, payload = {} } = req.body;

  if (!action_type || !target_entity_id) {
    res.status(400).json({ error: 'action_type and target_entity_id required' });
    return;
  }

  const validTypes: ActionType[] = [
    'reply_message', 'complete_task', 'send_draft',
    'apply_automation', 'create_asset', 'delegate', 'rest_action',
  ];
  if (!validTypes.includes(action_type)) {
    res.status(400).json({ error: `Invalid action_type: ${action_type}` });
    return;
  }

  const timestamp = now();
  const actionData: PendingActionData = {
    action_type,
    target_entity_id,
    payload,
    status: 'PENDING',
    created_at: timestamp,
    expires_at: timestamp + PENDING_ACTION_TIMEOUT_MS,
    confirmed_at: null,
  };

  const result = await createEntity('pending_action', actionData);
  storage.saveEntity(result.entity, result.state);
  storage.appendDelta(result.delta);

  res.json({
    id: result.entity.entity_id,
    action_type,
    target_entity_id,
    status: 'PENDING',
    token: getTokenForAction(action_type),
    expires_at: actionData.expires_at,
  });
});

// Confirm a pending action → triggers executor bridge
app.post('/api/actions/confirm/:id', async (req, res) => {
  const { id } = req.params;

  const entities = storage.loadEntitiesByType<PendingActionData>('pending_action');
  const found = entities.find(e => e.entity.entity_id === id);

  if (!found) {
    res.status(404).json({ error: 'Pending action not found' });
    return;
  }

  const state = found.state as PendingActionData;

  if (state.status !== 'PENDING') {
    res.status(409).json({ error: `Action already ${state.status}` });
    return;
  }

  // Check expiry
  if (now() > state.expires_at) {
    state.status = 'EXPIRED' as PendingActionStatus;
    storage.saveEntity(found.entity, state);
    res.status(410).json({ error: 'Action expired' });
    return;
  }

  // Mark confirmed
  state.status = 'CONFIRMED';
  state.confirmed_at = now();
  storage.saveEntity(found.entity, state);

  // Resolve context for the bridge
  let context: { task_title?: string; draft_data?: any } = {};

  if (state.action_type === 'complete_task') {
    // Look up the task title
    const allEntities = storage.loadAllEntities();
    for (const [_, data] of allEntities) {
      if (data.entity.entity_id === state.target_entity_id) {
        context.task_title = (data.state as Record<string, unknown>).title as string
          || (data.state as Record<string, unknown>).title_template as string
          || 'unknown';
        break;
      }
    }
  } else if (state.action_type === 'send_draft' || state.action_type === 'reply_message') {
    // Look up the draft data
    const drafts = storage.loadEntitiesByType('draft');
    const draft = drafts.find(d => d.entity.entity_id === state.target_entity_id);
    if (draft) {
      context.draft_data = draft.state;
    }
  }

  // Fire the executor bridge
  const bridgeResult = await bridgeAction(state, context);

  // Log to timeline
  timeline.emit('ACTION_EXECUTED', 'executor_bridge', {
    action_type: state.action_type,
    target_entity_id: state.target_entity_id,
    run_id: bridgeResult.run_id,
    status: bridgeResult.status,
    duration_ms: bridgeResult.duration_ms,
    error: bridgeResult.error,
  });

  res.json({
    id,
    status: 'CONFIRMED',
    execution: bridgeResult,
  });
});

// Cancel a pending action
app.post('/api/actions/cancel/:id', async (req, res) => {
  const { id } = req.params;

  const entities = storage.loadEntitiesByType<PendingActionData>('pending_action');
  const found = entities.find(e => e.entity.entity_id === id);

  if (!found) {
    res.status(404).json({ error: 'Pending action not found' });
    return;
  }

  const state = found.state as PendingActionData;

  if (state.status !== 'PENDING') {
    res.status(409).json({ error: `Action already ${state.status}` });
    return;
  }

  state.status = 'CANCELLED';
  storage.saveEntity(found.entity, state);

  res.json({ id, status: 'CANCELLED' });
});

// Check executor health
app.get('/api/executor/health', async (_req, res) => {
  const healthy = await checkExecutorHealth();
  res.json({ executor_reachable: healthy, url: process.env.UASC_EXECUTOR_URL || 'http://localhost:3008' });
});

type LifeSignals = {
  schema_version: string;
  generated_at: string;
  energy: {
    energy_level: number;
    mental_load: number;
    sleep_quality: number;
    burnout_risk: boolean;
    red_alert_active: boolean;
  };
  finance: {
    runway_months: number;
    monthly_income: number;
    monthly_expenses: number;
    money_delta: number;
  };
  skills: {
    utilization_pct: number;
    active_learning: boolean;
    mastery_count: number;
    growth_count: number;
  };
  network: {
    collaboration_score: number;
    active_relationships: number;
    outreach_this_week: number;
  };
  life_phase: number;
};

function clamp(val: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, val));
}

function loadSignals(): LifeSignals {
  const signalsPath = path.resolve(cognitiveSensorDir, 'life_signals.json');
  if (!fs.existsSync(signalsPath)) {
    return {
      schema_version: '1.0.0',
      generated_at: new Date().toISOString(),
      energy: { energy_level: 50, mental_load: 5, sleep_quality: 3, burnout_risk: false, red_alert_active: false },
      finance: { runway_months: 3.0, monthly_income: 0, monthly_expenses: 0, money_delta: 0 },
      skills: { utilization_pct: 50.0, active_learning: false, mastery_count: 0, growth_count: 0 },
      network: { collaboration_score: 30, active_relationships: 0, outreach_this_week: 0 },
      life_phase: 1,
    };
  }

  return JSON.parse(fs.readFileSync(signalsPath, 'utf-8')) as LifeSignals;
}

function saveSignals(signals: LifeSignals): void {
  signals.generated_at = new Date().toISOString();

  const signalsPath = path.resolve(cognitiveSensorDir, 'life_signals.json');
  fs.mkdirSync(path.dirname(signalsPath), { recursive: true });
  fs.writeFileSync(signalsPath, JSON.stringify(signals, null, 2));

  const domains: Array<keyof Pick<LifeSignals, 'energy' | 'finance' | 'skills' | 'network'>> = [
    'energy',
    'finance',
    'skills',
    'network',
  ];

  for (const domain of domains) {
    const metricsPath = path.resolve(cognitiveSensorDir, 'cycleboard', 'brain', `${domain}_metrics.json`);
    fs.mkdirSync(path.dirname(metricsPath), { recursive: true });
    fs.writeFileSync(
      metricsPath,
      JSON.stringify({
        generated_at: signals.generated_at,
        life_phase: signals.life_phase,
        ...signals[domain],
      }, null, 2),
    );
  }
}

app.get('/api/signals', (_req, res) => {
  res.json(loadSignals());
});

app.post('/api/signals/energy', (req, res) => {
  const body = req.body ?? {};
  const signals = loadSignals();

  if (typeof body.energy_level === 'number') {
    signals.energy.energy_level = clamp(body.energy_level, 0, 100);
  }
  if (typeof body.mental_load === 'number') {
    signals.energy.mental_load = clamp(body.mental_load, 1, 10);
  }
  if (typeof body.sleep_quality === 'number') {
    signals.energy.sleep_quality = clamp(body.sleep_quality, 1, 5);
  }
  if (typeof body.burnout_risk === 'boolean') {
    signals.energy.burnout_risk = body.burnout_risk;
  }
  if (typeof body.red_alert_active === 'boolean') {
    signals.energy.red_alert_active = body.red_alert_active;
  }

  saveSignals(signals);
  res.json(signals);
});

app.post('/api/signals/finance', (req, res) => {
  const body = req.body ?? {};
  const signals = loadSignals();

  if (typeof body.runway_months === 'number') {
    signals.finance.runway_months = Math.max(0, body.runway_months);
  }
  if (typeof body.monthly_income === 'number') {
    signals.finance.monthly_income = Math.max(0, body.monthly_income);
  }
  if (typeof body.monthly_expenses === 'number') {
    signals.finance.monthly_expenses = Math.max(0, body.monthly_expenses);
  }

  signals.finance.money_delta = signals.finance.monthly_income - signals.finance.monthly_expenses;

  saveSignals(signals);
  res.json(signals);
});

app.post('/api/signals/skills', (req, res) => {
  const body = req.body ?? {};
  const signals = loadSignals();

  if (typeof body.utilization_pct === 'number') {
    signals.skills.utilization_pct = clamp(body.utilization_pct, 0, 100);
  }
  if (typeof body.active_learning === 'boolean') {
    signals.skills.active_learning = body.active_learning;
  }
  if (typeof body.mastery_count === 'number') {
    signals.skills.mastery_count = Math.max(0, body.mastery_count);
  }
  if (typeof body.growth_count === 'number') {
    signals.skills.growth_count = Math.max(0, body.growth_count);
  }

  saveSignals(signals);
  res.json(signals);
});

app.post('/api/signals/network', (req, res) => {
  const body = req.body ?? {};
  const signals = loadSignals();

  if (typeof body.collaboration_score === 'number') {
    signals.network.collaboration_score = clamp(body.collaboration_score, 0, 100);
  }
  if (typeof body.active_relationships === 'number') {
    signals.network.active_relationships = Math.max(0, body.active_relationships);
  }
  if (typeof body.outreach_this_week === 'number') {
    signals.network.outreach_this_week = Math.max(0, body.outreach_this_week);
  }

  saveSignals(signals);
  res.json(signals);
});

app.post('/api/signals/bulk', (req, res) => {
  const body = req.body ?? {};
  const signals = loadSignals();

  if (body.energy && typeof body.energy === 'object') {
    if (typeof body.energy.energy_level === 'number') {
      signals.energy.energy_level = clamp(body.energy.energy_level, 0, 100);
    }
    if (typeof body.energy.mental_load === 'number') {
      signals.energy.mental_load = clamp(body.energy.mental_load, 1, 10);
    }
    if (typeof body.energy.sleep_quality === 'number') {
      signals.energy.sleep_quality = clamp(body.energy.sleep_quality, 1, 5);
    }
    if (typeof body.energy.burnout_risk === 'boolean') {
      signals.energy.burnout_risk = body.energy.burnout_risk;
    }
    if (typeof body.energy.red_alert_active === 'boolean') {
      signals.energy.red_alert_active = body.energy.red_alert_active;
    }
  }

  if (body.finance && typeof body.finance === 'object') {
    if (typeof body.finance.runway_months === 'number') {
      signals.finance.runway_months = Math.max(0, body.finance.runway_months);
    }
    if (typeof body.finance.monthly_income === 'number') {
      signals.finance.monthly_income = Math.max(0, body.finance.monthly_income);
    }
    if (typeof body.finance.monthly_expenses === 'number') {
      signals.finance.monthly_expenses = Math.max(0, body.finance.monthly_expenses);
    }
    signals.finance.money_delta = signals.finance.monthly_income - signals.finance.monthly_expenses;
  }

  if (body.skills && typeof body.skills === 'object') {
    if (typeof body.skills.utilization_pct === 'number') {
      signals.skills.utilization_pct = clamp(body.skills.utilization_pct, 0, 100);
    }
    if (typeof body.skills.active_learning === 'boolean') {
      signals.skills.active_learning = body.skills.active_learning;
    }
    if (typeof body.skills.mastery_count === 'number') {
      signals.skills.mastery_count = Math.max(0, body.skills.mastery_count);
    }
    if (typeof body.skills.growth_count === 'number') {
      signals.skills.growth_count = Math.max(0, body.skills.growth_count);
    }
  }

  if (body.network && typeof body.network === 'object') {
    if (typeof body.network.collaboration_score === 'number') {
      signals.network.collaboration_score = clamp(body.network.collaboration_score, 0, 100);
    }
    if (typeof body.network.active_relationships === 'number') {
      signals.network.active_relationships = Math.max(0, body.network.active_relationships);
    }
    if (typeof body.network.outreach_this_week === 'number') {
      signals.network.outreach_this_week = Math.max(0, body.network.outreach_this_week);
    }
  }

  if (typeof body.life_phase === 'number') {
    signals.life_phase = clamp(body.life_phase, 1, 5);
  }

  signals.finance.money_delta = signals.finance.monthly_income - signals.finance.monthly_expenses;

  saveSignals(signals);
  res.json(signals);
});

// Serve CycleBoard SPA
const resolvedPath = path.resolve(__dirname, '..', '..', '..', 'cognitive-sensor', 'cycleboard');
app.use('/cycleboard', express.static(resolvedPath));
const cognitiveSensorStaticPath = path.resolve(resolvedPath, '..');
app.use('/cognitive-sensor', express.static(cognitiveSensorStaticPath));
app.get(/^\/cycleboard(?:\/.*)?$/, (_req, res) => res.sendFile('index.html', { root: resolvedPath }));

// Start server
app.listen(PORT, '127.0.0.1', () => {
  console.log(`Delta-State Fabric API running at http://127.0.0.1:${PORT} (localhost only)`);
  console.log(`Data directory: ${dataDir}`);
});
