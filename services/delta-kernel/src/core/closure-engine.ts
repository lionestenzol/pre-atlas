/**
 * Closure Engine — shared by the API server (manual task/loop closes) and the
 * governance daemon (auto-tier prepared-action completions).
 *
 * Extracted from server.ts so autoExecutePreparedActions() in governance_daemon.ts
 * can drive the same closures registry / streak / closure-ratio / mode-transition
 * pipeline that PUT /api/tasks/:id already triggers on manual completion. Before
 * this extraction, auto-completed tasks bypassed this entirely — invisible to the
 * streak and closure-ratio machinery that mode governance reads.
 */

import * as path from 'path';
import * as fs from 'fs';
import { Storage } from '../cli/sqlite-storage';
import { createDelta, now } from './delta';
import type { TimelineLogger } from './timeline-logger.js';

export interface ClosureEngineDeps {
  storage: Storage;
  timeline: TimelineLogger;
  cognitiveSensorDir: string;
}

export interface ClosureInput {
  loop_id?: string;
  title?: string;
  outcome: 'closed' | 'archived';
}

export interface ClosureResult {
  success: boolean;
  mode?: string;
  mode_changed?: boolean;
  closureRatio?: number;
  closuresToday?: number;
  closedTotal?: number;
  openLoops?: number;
  buildAllowed?: boolean;
  streakDays?: number;
  streakUpdated?: boolean;
  bestStreak?: number;
}

export async function processClosureEvent(
  deps: ClosureEngineDeps,
  closureInput: ClosureInput
): Promise<ClosureResult> {
  const { storage, timeline, cognitiveSensorDir } = deps;
  const { loop_id, title, outcome } = closureInput;
  const timestamp = now();
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayStartTs = todayStart.getTime();
  const todayStr = todayStart.toISOString().split('T')[0];

  // Load closures registry
  const closuresPath = path.join(cognitiveSensorDir, 'closures.json');
  let closuresRegistry: {
    closures: Array<{ ts: number; loop_id: string | null; title: string | null; outcome: string; artifact_path?: string | null; coverage_score?: number | null; status?: string }>;
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
