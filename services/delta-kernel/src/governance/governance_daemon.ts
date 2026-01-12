/**
 * Governance Daemon
 *
 * Autonomous scheduler for ATLAS CORE governance tasks.
 * Runs heartbeat, refresh, and day boundary jobs on schedule.
 */

import cron from 'node-cron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { Storage } from '../cli/storage';
import { createDelta, createEntity, now } from '../core/delta';
import { WorkController } from '../core/work-controller';
import { getTimelineLogger, TimelineLogger } from '../core/timeline-logger.js';

// === TYPES ===

export type JobName = 'heartbeat' | 'refresh' | 'day_start' | 'day_end' | 'mode_recalc' | 'work_queue';

export interface JobRun {
  job: JobName;
  started_at: number;
  finished_at: number | null;
  status: 'running' | 'success' | 'failed';
  error?: string;
  output?: string;
}

export interface DaemonState {
  running: boolean;
  started_at: number | null;
  last_heartbeat: number | null;
  last_refresh: number | null;
  last_day_start: number | null;
  last_day_end: number | null;
  last_mode_recalc: number | null;
  last_work_queue: number | null;
  job_history: JobRun[];
  current_job: JobRun | null;
}

// === DAEMON CLASS ===

export class GovernanceDaemon {
  private storage: Storage;
  private repoRoot: string;
  private state: DaemonState;
  private cronJobs: cron.ScheduledTask[] = [];
  private refreshProcess: ChildProcess | null = null;
  private workController: WorkController;
  private timeline: TimelineLogger;

  // Schedule configuration
  private readonly HEARTBEAT_CRON = '*/5 * * * *';  // Every 5 minutes
  private readonly REFRESH_CRON = '0 * * * *';       // Every hour on the hour
  private readonly DAY_START_CRON = '0 6 * * *';     // 06:00 daily
  private readonly DAY_END_CRON = '0 22 * * *';      // 22:00 daily
  private readonly MODE_RECALC_CRON = '*/15 * * * *'; // Every 15 minutes — autonomous mode governance
  private readonly WORK_QUEUE_CRON = '*/1 * * * *';  // Every minute — work queue management
  private readonly REFRESH_TIMEOUT_MS = 120000;      // 2 minutes

  constructor(storage: Storage, repoRoot: string) {
    this.storage = storage;
    this.repoRoot = repoRoot;
    this.workController = new WorkController(repoRoot);
    this.timeline = getTimelineLogger(repoRoot);
    this.state = {
      running: false,
      started_at: null,
      last_heartbeat: null,
      last_refresh: null,
      last_day_start: null,
      last_day_end: null,
      last_mode_recalc: null,
      last_work_queue: null,
      job_history: [],
      current_job: null,
    };
  }

  /**
   * Start the daemon and all scheduled jobs.
   */
  start(): void {
    if (this.state.running) {
      console.log('[Daemon] Already running');
      return;
    }

    console.log('[Daemon] Starting governance daemon...');
    this.state.running = true;
    this.state.started_at = now();

    // Emit system start event
    this.timeline.emit('SYSTEM_START', 'governance_daemon', {
      timestamp: this.state.started_at,
    });

    // Schedule heartbeat (every 5 minutes)
    const heartbeatJob = cron.schedule(this.HEARTBEAT_CRON, () => {
      this.runJob('heartbeat');
    });
    this.cronJobs.push(heartbeatJob);

    // Schedule refresh (every hour)
    const refreshJob = cron.schedule(this.REFRESH_CRON, () => {
      this.runJob('refresh');
    });
    this.cronJobs.push(refreshJob);

    // Schedule day start (06:00)
    const dayStartJob = cron.schedule(this.DAY_START_CRON, () => {
      this.runJob('day_start');
    });
    this.cronJobs.push(dayStartJob);

    // Schedule day end (22:00)
    const dayEndJob = cron.schedule(this.DAY_END_CRON, () => {
      this.runJob('day_end');
    });
    this.cronJobs.push(dayEndJob);

    // Schedule autonomous mode recalculation (every 15 minutes)
    const modeRecalcJob = cron.schedule(this.MODE_RECALC_CRON, () => {
      this.runJob('mode_recalc');
    });
    this.cronJobs.push(modeRecalcJob);

    // Schedule work queue management (every minute)
    const workQueueJob = cron.schedule(this.WORK_QUEUE_CRON, () => {
      this.runJob('work_queue');
    });
    this.cronJobs.push(workQueueJob);

    // Run initial heartbeat immediately
    this.runJob('heartbeat');

    console.log('[Daemon] All jobs scheduled');
    console.log(`  - Heartbeat: ${this.HEARTBEAT_CRON}`);
    console.log(`  - Refresh: ${this.REFRESH_CRON}`);
    console.log(`  - Day Start: ${this.DAY_START_CRON}`);
    console.log(`  - Day End: ${this.DAY_END_CRON}`);
    console.log(`  - Mode Recalc: ${this.MODE_RECALC_CRON}`);
    console.log(`  - Work Queue: ${this.WORK_QUEUE_CRON}`);
  }

  /**
   * Stop the daemon and cancel all scheduled jobs.
   */
  stop(): void {
    if (!this.state.running) {
      console.log('[Daemon] Not running');
      return;
    }

    console.log('[Daemon] Stopping governance daemon...');

    // Cancel all cron jobs
    for (const job of this.cronJobs) {
      job.stop();
    }
    this.cronJobs = [];

    // Kill any running refresh process
    if (this.refreshProcess) {
      this.refreshProcess.kill();
      this.refreshProcess = null;
    }

    this.state.running = false;
    console.log('[Daemon] Stopped');
  }

  /**
   * Get current daemon status.
   */
  getStatus(): DaemonState {
    return { ...this.state };
  }

  /**
   * Manually trigger a job.
   */
  async runJob(jobName: JobName): Promise<JobRun> {
    const run: JobRun = {
      job: jobName,
      started_at: now(),
      finished_at: null,
      status: 'running',
    };

    this.state.current_job = run;
    this.addToHistory(run);

    console.log(`[Daemon] Running job: ${jobName}`);

    try {
      switch (jobName) {
        case 'heartbeat':
          await this.runHeartbeat();
          break;
        case 'refresh':
          await this.runRefresh();
          break;
        case 'day_start':
          await this.runDayStart();
          break;
        case 'day_end':
          await this.runDayEnd();
          break;
        case 'mode_recalc':
          await this.runModeRecalc();
          break;
        case 'work_queue':
          await this.runWorkQueue();
          break;
      }

      run.status = 'success';
      run.finished_at = now();
      this.updateLastRun(jobName, run.finished_at);
      console.log(`[Daemon] Job ${jobName} completed successfully`);

    } catch (error) {
      run.status = 'failed';
      run.finished_at = now();
      run.error = (error as Error).message;
      console.error(`[Daemon] Job ${jobName} failed:`, run.error);
    }

    this.state.current_job = null;
    this.updateHistoryEntry(run);

    return run;
  }

  // === JOB IMPLEMENTATIONS ===

  /**
   * Heartbeat: Update daemon.last_heartbeat in system_state.
   */
  private async runHeartbeat(): Promise<void> {
    const timestamp = now();
    await this.updateSystemState({
      'daemon.last_heartbeat': timestamp,
      'daemon.running': true,
    });

    // Emit heartbeat event (sparse — only on 5-min boundaries)
    this.timeline.emit('DAEMON_HEARTBEAT', 'governance_daemon', {
      timestamp,
    });
  }

  /**
   * Refresh: Spawn Python refresh.py with timeout.
   */
  private async runRefresh(): Promise<void> {
    const refreshPath = path.join(this.repoRoot, 'services', 'cognitive-sensor', 'refresh.py');

    if (!fs.existsSync(refreshPath)) {
      throw new Error(`refresh.py not found at: ${refreshPath}`);
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this.refreshProcess) {
          this.refreshProcess.kill();
          this.refreshProcess = null;
        }
        reject(new Error(`Refresh timed out after ${this.REFRESH_TIMEOUT_MS}ms`));
      }, this.REFRESH_TIMEOUT_MS);

      this.refreshProcess = spawn('python', [refreshPath], {
        cwd: path.dirname(refreshPath),
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      this.refreshProcess.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      this.refreshProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      this.refreshProcess.on('close', async (code) => {
        clearTimeout(timeout);
        this.refreshProcess = null;

        if (code === 0) {
          // Update system state with refresh timestamp
          await this.updateSystemState({
            'daemon.last_refresh': now(),
            'daemon.refresh_output': stdout.slice(-500), // Last 500 chars
          });
          resolve();
        } else {
          reject(new Error(`refresh.py exited with code ${code}: ${stderr}`));
        }
      });

      this.refreshProcess.on('error', (err) => {
        clearTimeout(timeout);
        this.refreshProcess = null;
        reject(err);
      });
    });
  }

  /**
   * Day Start: Record start-of-day marker + reset daily counters + mode recalc.
   */
  private async runDayStart(): Promise<void> {
    const timestamp = now();
    const today = new Date().toISOString().split('T')[0];

    // Reset daily closure counter in closures.json
    const closuresPath = path.join(this.repoRoot, 'services/cognitive-sensor/closures.json');
    try {
      if (fs.existsSync(closuresPath)) {
        const registry = JSON.parse(fs.readFileSync(closuresPath, 'utf-8'));
        registry.stats.closures_today = 0;
        fs.writeFileSync(closuresPath, JSON.stringify(registry, null, 2));
      }
    } catch {
      // Best effort
    }

    // Run mode recalculation at day start
    const modeResult = await this.recalculateModeAndApply();

    await this.updateSystemState({
      'day.current_date': today,
      'day.started_at': timestamp,
      'day.status': 'active',
      'day.mode_at_start': modeResult.mode,
      'metrics.closures_today': 0,
    });

    console.log(`[Daemon] Day start: ${today}, mode: ${modeResult.mode}`);
  }

  /**
   * Day End: Record end-of-day marker + STREAK SOVEREIGNTY (Step 4)
   *
   * If no closures occurred today AND mode is not BUILD/SCALE, reset streak to 0.
   * This prevents streak inflation from days without productive closure.
   */
  private async runDayEnd(): Promise<void> {
    const timestamp = now();
    const todayStr = new Date().toISOString().split('T')[0];

    // Read closures registry to check today's closures
    const closuresPath = path.join(this.repoRoot, 'services/cognitive-sensor/closures.json');
    let closuresToday = 0;
    let lastStreakDate: string | null = null;

    try {
      if (fs.existsSync(closuresPath)) {
        const registry = JSON.parse(fs.readFileSync(closuresPath, 'utf-8'));
        closuresToday = registry.stats?.closures_today ?? 0;
        lastStreakDate = registry.stats?.last_streak_date ?? null;
      }
    } catch {
      // Use defaults
    }

    // Get current mode from system state
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');
    const currentMode = entities.length > 0 ? (entities[0].state.mode as string) || 'CLOSURE' : 'CLOSURE';
    const currentStreakDays = entities.length > 0 ? (entities[0].state.streak_days as number) || 0 : 0;

    // STREAK SOVEREIGNTY: Reset if no closures today OR not in BUILD/SCALE mode
    let streakReset = false;
    let newStreakDays = currentStreakDays;

    // Only reset if today wasn't a productive BUILD day
    // (lastStreakDate !== todayStr means no closure incremented streak today)
    if (lastStreakDate !== todayStr && currentStreakDays > 0) {
      // No productive closure today — reset streak
      newStreakDays = 0;
      streakReset = true;

      // Also update closures.json registry
      try {
        if (fs.existsSync(closuresPath)) {
          const registry = JSON.parse(fs.readFileSync(closuresPath, 'utf-8'));
          registry.stats.streak_days = 0;
          registry.stats.closures_today = 0; // Reset daily counter
          fs.writeFileSync(closuresPath, JSON.stringify(registry, null, 2));
        }
      } catch {
        // Best effort
      }
    }

    // Run mode recalculation at day end
    const modeResult = await this.recalculateModeAndApply();

    await this.updateSystemState({
      'day.ended_at': timestamp,
      'day.status': 'closed',
      'day.closures_count': closuresToday,
      'streak_days': newStreakDays,
      'day.streak_reset': streakReset,
      'day.mode_at_end': modeResult.mode,
    });

    if (streakReset) {
      console.log(`[Daemon] Streak reset to 0 (no productive BUILD closure today)`);
    }
  }

  /**
   * Mode Recalculation: Autonomous mode governance every 15 minutes.
   * Reads cognitive state and applies mode rules without requiring a closure event.
   */
  private async runModeRecalc(): Promise<void> {
    const result = await this.recalculateModeAndApply();
    console.log(`[Daemon] Mode recalc: ${result.previousMode} → ${result.mode} (ratio: ${(result.closureRatio * 100).toFixed(1)}%)`);
  }

  /**
   * Work Queue: Check for timed-out jobs and advance the queue.
   * Runs every minute to ensure responsive job management.
   */
  private async runWorkQueue(): Promise<void> {
    const result = this.workController.checkTimeouts();

    if (result.timed_out.length > 0) {
      console.log(`[Daemon] Work queue: ${result.timed_out.length} job(s) timed out: ${result.timed_out.join(', ')}`);
    }

    if (result.advanced.length > 0) {
      console.log(`[Daemon] Work queue: ${result.advanced.length} job(s) advanced from queue: ${result.advanced.join(', ')}`);
    }

    // Update system state with work queue stats
    const ledger = this.workController.getLedger();
    await this.updateSystemState({
      'work.active_count': ledger.active.length,
      'work.queued_count': ledger.queued.length,
      'work.total_completed': ledger.stats.total_completed,
      'work.total_cost_usd': ledger.stats.total_cost_usd,
      'work.last_check_at': now(),
    });
  }

  /**
   * AUTONOMOUS MODE ENGINE
   *
   * Reads cognitive state, computes closure ratio, applies mode rules.
   * Returns whether mode changed and the new state.
   */
  private async recalculateModeAndApply(): Promise<{
    mode: string;
    previousMode: string;
    modeChanged: boolean;
    closureRatio: number;
    openLoops: number;
    buildAllowed: boolean;
  }> {
    const timestamp = now();

    // Read cognitive state
    const cognitiveStatePath = path.join(this.repoRoot, 'services/cognitive-sensor/cognitive_state.json');
    const closuresPath = path.join(this.repoRoot, 'services/cognitive-sensor/closures.json');

    let openLoops = 0;
    let closedLoops = 0;

    try {
      if (fs.existsSync(cognitiveStatePath)) {
        const cogState = JSON.parse(fs.readFileSync(cognitiveStatePath, 'utf-8'));
        openLoops = cogState.closure?.open ?? 0;
      }
    } catch {
      // Use default
    }

    try {
      if (fs.existsSync(closuresPath)) {
        const registry = JSON.parse(fs.readFileSync(closuresPath, 'utf-8'));
        closedLoops = registry.stats?.total_closures ?? 0;
      }
    } catch {
      // Use default
    }

    // Compute closure ratio
    const totalLoops = openLoops + closedLoops;
    const closureRatio = totalLoops > 0 ? closedLoops / totalLoops : 1;

    // Apply mode rules (same as close_loop)
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

    // Get current mode
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');
    const previousMode = entities.length > 0 ? (entities[0].state.mode as string) || 'CLOSURE' : 'CLOSURE';
    const modeChanged = previousMode !== newMode;

    // Apply updates if mode changed or metrics need refresh
    const updates: Record<string, unknown> = {
      'metrics.closure_ratio': closureRatio,
      'metrics.open_loops': openLoops,
      'metrics.closed_loops_total': closedLoops,
      'metrics.last_recalc_at': timestamp,
      'build_allowed': buildAllowed,
    };

    if (modeChanged) {
      updates['mode'] = newMode;
      updates['last_mode_transition_at'] = timestamp;
      updates['last_mode_transition_reason'] = `Autonomous recalc: ratio=${closureRatio.toFixed(2)}`;

      // Emit MODE_CHANGED event
      this.timeline.emit('MODE_CHANGED', 'governance_daemon', {
        previous_mode: previousMode,
        new_mode: newMode,
        closure_ratio: closureRatio,
        open_loops: openLoops,
        build_allowed: buildAllowed,
      });
    }

    await this.updateSystemState(updates);

    return {
      mode: newMode,
      previousMode,
      modeChanged,
      closureRatio,
      openLoops,
      buildAllowed,
    };
  }

  // === HELPERS ===

  /**
   * Update system_state entity with new fields.
   * Handles nested paths like 'daemon.last_heartbeat' by ensuring parent objects exist.
   */
  private async updateSystemState(fields: Record<string, unknown>): Promise<void> {
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');

    // Convert dot notation to nested object
    const expandFields = (flat: Record<string, unknown>): Record<string, unknown> => {
      const result: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(flat)) {
        const parts = key.split('.');
        let current = result;
        for (let i = 0; i < parts.length - 1; i++) {
          if (!(parts[i] in current)) {
            current[parts[i]] = {};
          }
          current = current[parts[i]] as Record<string, unknown>;
        }
        current[parts[parts.length - 1]] = value;
      }
      return result;
    };

    if (entities.length > 0) {
      const existing = entities[0];
      const expandedFields = expandFields(fields);

      // Merge expanded fields into existing state
      const mergeDeep = (target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> => {
        for (const key of Object.keys(source)) {
          if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
            if (!target[key] || typeof target[key] !== 'object') {
              target[key] = {};
            }
            mergeDeep(target[key] as Record<string, unknown>, source[key] as Record<string, unknown>);
          } else {
            target[key] = source[key];
          }
        }
        return target;
      };

      const newState = mergeDeep({ ...existing.state }, expandedFields);

      // Create delta with top-level keys that changed
      const changedKeys = Object.keys(expandedFields);
      const result = await createDelta(
        existing.entity,
        existing.state,
        changedKeys.map((key) => ({
          op: 'replace' as const,
          path: `/${key}`,
          value: newState[key],
        })),
        'governance_daemon'
      );
      this.storage.saveEntity(result.entity, result.state);
      this.storage.appendDelta(result.delta);
    } else {
      // Create new system_state with expanded fields
      const expandedFields = expandFields(fields);
      const result = await createEntity('system_state', expandedFields);
      this.storage.saveEntity(result.entity, result.state);
      this.storage.appendDelta(result.delta);
    }
  }

  private updateLastRun(jobName: JobName, timestamp: number): void {
    switch (jobName) {
      case 'heartbeat':
        this.state.last_heartbeat = timestamp;
        break;
      case 'refresh':
        this.state.last_refresh = timestamp;
        break;
      case 'day_start':
        this.state.last_day_start = timestamp;
        break;
      case 'day_end':
        this.state.last_day_end = timestamp;
        break;
      case 'mode_recalc':
        this.state.last_mode_recalc = timestamp;
        break;
      case 'work_queue':
        this.state.last_work_queue = timestamp;
        break;
    }
  }

  private addToHistory(run: JobRun): void {
    this.state.job_history.unshift(run);
    // Keep only last 50 entries
    if (this.state.job_history.length > 50) {
      this.state.job_history = this.state.job_history.slice(0, 50);
    }
  }

  private updateHistoryEntry(run: JobRun): void {
    const index = this.state.job_history.findIndex(
      (r) => r.started_at === run.started_at && r.job === run.job
    );
    if (index !== -1) {
      this.state.job_history[index] = run;
    }
  }
}

// Singleton instance
let daemonInstance: GovernanceDaemon | null = null;

/**
 * Get or create the daemon instance.
 */
export function getDaemon(storage: Storage, repoRoot: string): GovernanceDaemon {
  if (!daemonInstance) {
    daemonInstance = new GovernanceDaemon(storage, repoRoot);
  }
  return daemonInstance;
}
