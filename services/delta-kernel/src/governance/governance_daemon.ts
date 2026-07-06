/**
 * Governance Daemon
 *
 * Autonomous scheduler for ATLAS CORE governance tasks.
 * Runs heartbeat, refresh, and day boundary jobs on schedule.
 */

import * as cron from 'node-cron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { Storage } from '../cli/sqlite-storage';
import { createDelta, createEntity, now } from '../core/delta';
import { route } from '../core/routing';
import { Mode, SystemStateData, ActionType, InboxData, TaskData, ThreadData, DraftData, PendingActionData, EntityType } from '../core/types';
import { WorkController } from '../core/work-controller';
import { getTimelineLogger, TimelineLogger } from '../core/timeline-logger.js';
import { getEffectiveRiskTier, buildCockpit, createPendingAction, CockpitBuildContext } from '../core/cockpit.js';
import { emitEvent } from '../core/event-emitter.js';
import { notifyPhone } from '../core/notify.js';

// === TYPES ===

export type JobName = 'heartbeat' | 'refresh' | 'day_start' | 'day_end' | 'mode_recalc' | 'work_queue' | 'agent_pipeline' | 'preparation' | 'stall_check' | 'sensor_daily';

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
  last_agent_pipeline: number | null;
  last_preparation: number | null;
  last_stall_check: number | null;
  last_sensor_daily: number | null;
  job_history: JobRun[];
  current_job: JobRun | null;
}

// === DAEMON CLASS ===

export class GovernanceDaemon {
  private storage: Storage;
  private repoRoot: string;
  private cognitiveSensorDir: string;
  private state: DaemonState;
  private cronJobs: cron.ScheduledTask[] = [];
  private refreshProcess: ChildProcess | null = null;
  private agentProcess: ChildProcess | null = null;
  private sensorProcess: ChildProcess | null = null;
  private workController: WorkController;
  private timeline: TimelineLogger;

  // Schedule configuration
  private readonly HEARTBEAT_CRON = '*/5 * * * *';  // Every 5 minutes
  private readonly REFRESH_CRON = '0 * * * *';       // Every hour on the hour
  private readonly DAY_START_CRON = '0 6 * * *';     // 06:00 daily
  private readonly DAY_END_CRON = '0 22 * * *';      // 22:00 daily
  private readonly MODE_RECALC_CRON = '*/15 * * * *'; // Every 15 minutes — autonomous mode governance
  private readonly WORK_QUEUE_CRON = '*/1 * * * *';  // Every minute — work queue management
  private readonly AGENT_PIPELINE_CRON = '0 6 * * 0'; // Sunday 06:00 — weekly idea pipeline
  private readonly PREPARATION_CRON = '*/5 * * * *';  // Every 5 minutes — preparation engine
  private readonly STALL_CHECK_CRON = '0 21 * * *';   // 21:00 daily — stall detection
  private readonly SENSOR_DAILY_CRON = '45 5 * * *';  // 05:45 daily — cognitive-sensor pipeline, ahead of Day Start
  private readonly REFRESH_TIMEOUT_MS = 120000;       // 2 minutes
  private readonly AGENT_PIPELINE_TIMEOUT_MS = 600000; // 10 minutes
  private readonly SENSOR_DAILY_TIMEOUT_MS = 900000;   // 15 minutes — multi-phase pipeline (ingest, es_scan, triage, backlog); measured >5min in practice

  constructor(storage: Storage, repoRoot: string) {
    this.storage = storage;
    this.repoRoot = repoRoot;
    this.cognitiveSensorDir = process.env.COGNITIVE_SENSOR_DIR || path.join(repoRoot, 'services', 'cognitive-sensor');
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
      last_agent_pipeline: null,
      last_preparation: null,
      last_stall_check: null,
      last_sensor_daily: null,
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

    // noOverlap:true on every job below — verified 2026-07-06 (adversarial review of
    // f6a0c61) that node-cron 4.2.1 defaults noOverlap to false, so a slow tick (e.g.
    // work_queue's notifyPreparedActions looping over up to 7 prepared actions with
    // an awaited hash per entity) could otherwise overlap the next tick and race the
    // in-memory pending_action dedup check against not-yet-persisted writes, creating
    // duplicate pending actions + duplicate phone notifications for the same target.
    // Every job here re-derives its state from current data each run, so skipping an
    // overlapped tick (node-cron's behavior with noOverlap:true) is always correct —
    // nothing here needs to "catch up" a missed tick.

    // Schedule heartbeat (every 5 minutes)
    const heartbeatJob = cron.schedule(this.HEARTBEAT_CRON, () => {
      this.runJob('heartbeat');
    }, { noOverlap: true, name: 'heartbeat' });
    this.cronJobs.push(heartbeatJob);

    // Schedule refresh (every hour)
    const refreshJob = cron.schedule(this.REFRESH_CRON, () => {
      this.runJob('refresh');
    }, { noOverlap: true, name: 'refresh' });
    this.cronJobs.push(refreshJob);

    // Schedule day start (06:00)
    const dayStartJob = cron.schedule(this.DAY_START_CRON, () => {
      this.runJob('day_start');
    }, { noOverlap: true, name: 'day_start' });
    this.cronJobs.push(dayStartJob);

    // Schedule day end (22:00)
    const dayEndJob = cron.schedule(this.DAY_END_CRON, () => {
      this.runJob('day_end');
    }, { noOverlap: true, name: 'day_end' });
    this.cronJobs.push(dayEndJob);

    // Schedule autonomous mode recalculation (every 15 minutes)
    const modeRecalcJob = cron.schedule(this.MODE_RECALC_CRON, () => {
      this.runJob('mode_recalc');
    }, { noOverlap: true, name: 'mode_recalc' });
    this.cronJobs.push(modeRecalcJob);

    // Schedule work queue management (every minute)
    const workQueueJob = cron.schedule(this.WORK_QUEUE_CRON, () => {
      this.runJob('work_queue');
    }, { noOverlap: true, name: 'work_queue' });
    this.cronJobs.push(workQueueJob);

    // Schedule agent pipeline (weekly Sunday 06:00)
    const agentPipelineJob = cron.schedule(this.AGENT_PIPELINE_CRON, () => {
      this.runJob('agent_pipeline');
    }, { noOverlap: true, name: 'agent_pipeline' });
    this.cronJobs.push(agentPipelineJob);

    // Schedule preparation engine (every 5 minutes)
    const preparationJob = cron.schedule(this.PREPARATION_CRON, () => {
      this.runJob('preparation');
    }, { noOverlap: true, name: 'preparation' });
    this.cronJobs.push(preparationJob);

    // Schedule stall detection (21:00 daily)
    const stallCheckJob = cron.schedule(this.STALL_CHECK_CRON, () => {
      this.runJob('stall_check');
    }, { noOverlap: true, name: 'stall_check' });
    this.cronJobs.push(stallCheckJob);

    // Schedule cognitive-sensor's daily pipeline (05:45, ahead of Day Start at
    // 06:00) — this was the unscheduled front of the spine per the 2026-07-06
    // completeness assessment: Optogon/cortex had nothing feeding them.
    const sensorDailyJob = cron.schedule(this.SENSOR_DAILY_CRON, () => {
      this.runJob('sensor_daily');
    }, { noOverlap: true, name: 'sensor_daily' });
    this.cronJobs.push(sensorDailyJob);

    // Run initial heartbeat immediately
    this.runJob('heartbeat');

    console.log('[Daemon] All jobs scheduled');
    console.log(`  - Heartbeat: ${this.HEARTBEAT_CRON}`);
    console.log(`  - Refresh: ${this.REFRESH_CRON}`);
    console.log(`  - Day Start: ${this.DAY_START_CRON}`);
    console.log(`  - Day End: ${this.DAY_END_CRON}`);
    console.log(`  - Mode Recalc: ${this.MODE_RECALC_CRON}`);
    console.log(`  - Work Queue: ${this.WORK_QUEUE_CRON}`);
    console.log(`  - Agent Pipeline: ${this.AGENT_PIPELINE_CRON}`);
    console.log(`  - Preparation: ${this.PREPARATION_CRON}`);
    console.log(`  - Stall Check: ${this.STALL_CHECK_CRON}`);
    console.log(`  - Sensor Daily: ${this.SENSOR_DAILY_CRON}`);
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

    // Kill any running processes
    if (this.refreshProcess) {
      this.refreshProcess.kill();
      this.refreshProcess = null;
    }
    if (this.agentProcess) {
      this.agentProcess.kill();
      this.agentProcess = null;
    }
    if (this.sensorProcess) {
      this.sensorProcess.kill();
      this.sensorProcess = null;
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
        case 'agent_pipeline':
          await this.runAgentPipeline();
          break;
        case 'preparation':
          await this.runPreparation();
          break;
        case 'stall_check':
          await this.runStallCheck();
          break;
        case 'sensor_daily':
          await this.runSensorDaily();
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
    const MAX_RETRIES = 2;
    const RETRY_DELAY_MS = 5000;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        await this.executeRefresh();
        return;
      } catch (error) {
        if (attempt < MAX_RETRIES) {
          console.log(`[Daemon] Refresh attempt ${attempt + 1} failed, retrying in ${RETRY_DELAY_MS}ms...`);
          await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        } else {
          throw error;
        }
      }
    }
  }

  private executeRefresh(): Promise<void> {
    const refreshPath = path.join(this.cognitiveSensorDir, 'refresh.py');

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
    const closuresPath = path.join(this.cognitiveSensorDir, 'closures.json');
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

    // Seed inPACT's Today screen from what Atlas already knows, instead of
    // leaving Bruke to author a blank plan every morning (see TRUST_BOUNDARY.md-
    // adjacent completeness assessment, 2026-07-06).
    await this.seedTodayPlan(today);

    console.log(`[Daemon] Day start: ${today}, mode: ${modeResult.mode}`);
  }

  /**
   * Pre-fill inPACT's Today.daily[date] with real open tasks (top 3 by priority)
   * so the screen arrives with content instead of starting blank. Never invents
   * winTarget/why/lever — those need Bruke's own judgment, not a guess. Skips
   * entirely if a plan for `date` already exists (never clobbers in-progress work)
   * or if there's no cycle_board entity yet, or no open tasks to seed with.
   */
  private async seedTodayPlan(date: string): Promise<void> {
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('cycle_board');
    if (entities.length === 0) return;

    const existing = entities[0];
    const cbData = (existing.state as Record<string, unknown>).data as Record<string, unknown> | undefined;
    if (!cbData) return;

    const todayBlock = (cbData.Today as Record<string, unknown>) || { mission: '', motto: '', daily: {} };
    const daily = (todayBlock.daily as Record<string, unknown>) || {};
    if (daily[date]) return;

    const priorityRank: Record<string, number> = { CRITICAL: 0, HIGH: 1, NORMAL: 2, LOW: 3 };
    const tasks = this.storage.loadEntitiesByType<Record<string, unknown>>('task');
    const openTasks = tasks
      .filter((t) => {
        const status = (t.state as Record<string, unknown>).status as string;
        return status !== 'DONE' && status !== 'ARCHIVED';
      })
      .sort((a, b) => {
        const pa = priorityRank[(a.state as Record<string, unknown>).priority as string] ?? 4;
        const pb = priorityRank[(b.state as Record<string, unknown>).priority as string] ?? 4;
        return pa - pb;
      })
      .slice(0, 3);

    if (openTasks.length === 0) return;

    const titleOf = (t: { state: Record<string, unknown> }): string =>
      (t.state.title as string) || (t.state.title_template as string) || 'Untitled task';

    const idOf = (t: { entity: { entity_id: string } }): string => t.entity.entity_id;

    const seededPlan = {
      date,
      winTarget: '',
      p1: titleOf(openTasks[0]), p1why: '', p1TaskId: idOf(openTasks[0]),
      p2: openTasks[1] ? titleOf(openTasks[1]) : '', p2why: '', p2TaskId: openTasks[1] ? idOf(openTasks[1]) : '',
      p3: openTasks[2] ? titleOf(openTasks[2]) : '', p3why: '', p3TaskId: openTasks[2] ? idOf(openTasks[2]) : '',
      x1: '', y1: '', x2: '', y2: '', x3: '', y3: '',
      lever: '', resetMove: '', reflection: '',
      updated_at: null,
      seeded_from_atlas: true,
    };

    const newCbData = {
      ...cbData,
      Today: {
        ...todayBlock,
        daily: { ...daily, [date]: seededPlan },
      },
      _localUpdatedAt: new Date().toISOString(),
    };

    const result = await createDelta(
      existing.entity,
      existing.state,
      [{ op: 'replace' as const, path: '/data', value: newCbData }],
      'governance_daemon'
    );
    this.storage.saveEntity(result.entity, result.state);
    this.storage.appendDelta(result.delta);

    const summary = openTasks.map(titleOf).join(' · ');
    notifyPhone('Today seeded', summary).catch(() => {});
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
    const closuresPath = path.join(this.cognitiveSensorDir, 'closures.json');
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

    // Auto-execute prepared actions with 'auto' risk tier
    await this.autoExecutePreparedActions();

    // Create pending_action + phone notify for notify/confirm-tier prepared actions
    await this.notifyPreparedActions();
  }

  /**
   * Phase 3B: Auto-execute prepared actions that have 'auto' risk tier.
   * Reads governance config for safety toggles, respects rate limits.
   */
  private async autoExecutePreparedActions(): Promise<void> {
    // Read governance config for auto_execution settings
    const configPath = path.join(this.cognitiveSensorDir, 'governance_config.json');
    let autoConfig = { enabled: false, max_per_cycle: 3, max_per_day: 10 };

    try {
      if (fs.existsSync(configPath)) {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        const ae = config.auto_execution;
        if (ae) {
          autoConfig = {
            enabled: ae.enabled !== false,
            max_per_cycle: ae.max_per_cycle ?? 3,
            max_per_day: ae.max_per_day ?? 10,
          };
        }
      }
    } catch { /* use defaults */ }

    if (!autoConfig.enabled) return;

    // Read daily counter from system state
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');
    const systemState = entities.length > 0 ? entities[0].state : {};
    const currentMode = ((systemState as Record<string, unknown>).mode as Mode) || 'CLOSURE';
    const autoExecToday = ((systemState as Record<string, unknown>).auto_executions_today as number) || 0;

    if (autoExecToday >= autoConfig.max_per_day) return;

    // Load latest preparation result
    const prepEntities = this.storage.loadEntitiesByType<Record<string, unknown>>('preparation_result');
    if (prepEntities.length === 0) return;

    const prepData = prepEntities[0].state;
    const taskTriage = (prepData.taskTriage as Array<{ task_id?: string; entity_id?: string; task_title?: string; label?: string }>) || [];

    let executedThisCycle = 0;

    for (const triaged of taskTriage) {
      if (executedThisCycle >= autoConfig.max_per_cycle) break;
      if (autoExecToday + executedThisCycle >= autoConfig.max_per_day) break;

      // Check if complete_task is auto-tier in current mode
      const effectiveTier = getEffectiveRiskTier('complete_task', currentMode);
      if (effectiveTier !== 'auto') continue;

      const taskId = triaged.task_id || triaged.entity_id;
      if (!taskId) continue;

      // Find and complete the task
      const allEntities = this.storage.loadAllEntities();
      let taskCompleted = false;

      for (const [, data] of allEntities) {
        if (data.entity.entity_id === taskId) {
          const taskState = data.state as Record<string, unknown>;
          if (taskState.status === 'DONE' || taskState.status === 'ARCHIVED') break;

          taskState.status = 'DONE';
          taskState.closed_at = now();
          taskState.closed_by = 'auto_execution';
          this.storage.saveEntity(data.entity, taskState);
          taskCompleted = true;
          break;
        }
      }

      if (taskCompleted) {
        executedThisCycle++;
        const title = triaged.task_title || triaged.label || 'Task';

        this.timeline.emit('AUTO_EXECUTED', 'governance_daemon', {
          action_type: 'complete_task',
          entity_id: taskId,
          title,
          mode: currentMode,
          risk_tier: 'auto',
        });

        console.log(`[Daemon] Auto-executed: complete_task "${title}"`);
      }
    }

    if (executedThisCycle > 0) {
      await this.updateSystemState({
        'auto_executions_today': autoExecToday + executedThisCycle,
        'daemon.last_auto_execution': now(),
      });
    }
  }

  /**
   * Phase 3C: create pending_action entities (+ phone notify) for prepared
   * actions whose effective risk tier is 'notify' or 'confirm' — this is the
   * first caller createPendingAction has ever had in the repo. 'auto'-tier
   * actions stay on autoExecutePreparedActions()'s existing path above.
   * Dedup: skip any entity that already has a PENDING pending_action, so the
   * same task doesn't spawn a fresh one on every minute's tick.
   */
  private async notifyPreparedActions(): Promise<void> {
    const systemStateEntities = this.storage.loadEntitiesByType<SystemStateData>('system_state');
    if (systemStateEntities.length === 0) return;
    const systemState = systemStateEntities[0];
    const mode = systemState.state.mode as Mode;

    const inboxEntities = this.storage.loadEntitiesByType<InboxData>('inbox');
    const inbox = inboxEntities.length > 0
      ? inboxEntities[0]
      : {
          entity: {
            entity_id: 'synthetic-inbox-governance',
            entity_type: 'inbox' as EntityType,
            created_at: now(),
            current_version: 1,
            current_hash: '',
            is_archived: false,
          },
          state: {
            unread_count: 0,
            priority_queue: [],
            task_queue: [],
            idea_queue: [],
            last_activity_at: now(),
          } satisfies InboxData,
        };

    const tasks = this.storage.loadEntitiesByType<TaskData>('task');
    const threads = this.storage.loadEntitiesByType<ThreadData>('thread');
    const drafts = this.storage.loadEntitiesByType<DraftData>('draft');
    const existingPending = this.storage.loadEntitiesByType<PendingActionData>('pending_action');

    const ctx: CockpitBuildContext = {
      systemState,
      inbox,
      tasks,
      threads,
      drafts,
      pendingAction: existingPending.length > 0 ? existingPending[0] : null,
    };

    const cockpit = buildCockpit(ctx);

    const targetsAwaitingConfirmation = new Set(
      existingPending
        .filter((e) => e.state.status === 'PENDING')
        .map((e) => e.state.target_entity_id)
    );

    for (const action of cockpit.prepared_actions) {
      const tier = getEffectiveRiskTier(action.action_type as ActionType, mode);
      if (tier === 'auto') continue;
      if (targetsAwaitingConfirmation.has(action.entity_id)) continue;

      // Per-action isolation (added 2026-07-06 after adversarial review of f6a0c61):
      // a thrown error here previously propagated out of the whole loop, silently
      // dropping every remaining prepared action for this tick with no per-action
      // visibility. Each action now fails independently — the tick's dedup Set
      // already reflects everything that succeeded, so a skipped action is just
      // retried on the next minute's tick.
      try {
        const result = await createPendingAction(action, 'governance_daemon');
        this.storage.saveEntity(result.entity, result.state);
        this.storage.appendDelta(result.delta);
        targetsAwaitingConfirmation.add(action.entity_id);

        this.timeline.emit('PENDING_ACTION_CREATED', 'governance_daemon', {
          pending_id: result.entity.entity_id,
          action_type: action.action_type,
          entity_id: action.entity_id,
          label: action.label,
          risk_tier: tier,
          mode,
        });

        notifyPhone(
          tier === 'confirm' ? 'Action needs confirmation' : 'Action ready',
          action.label
        ).catch(() => {});

        console.log(`[Daemon] Pending action created (${tier}): "${action.label}"`);
      } catch (error) {
        console.error(`[Daemon] Failed to create pending action for "${action.label}":`, (error as Error).message);
      }
    }
  }

  /**
   * Agent Pipeline: Run the 5-agent idea processing pipeline weekly.
   * Spawns run_agents.py with a 10-minute timeout.
   */
  private async runAgentPipeline(): Promise<void> {
    const MAX_RETRIES = 1;
    const RETRY_DELAY_MS = 10000;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        await this.executeAgentPipeline();

        // After pipeline completes, auto-promote top ideas to tasks (Phase 4A)
        await this.autoPromoteIdeas();

        return;
      } catch (error) {
        if (attempt < MAX_RETRIES) {
          console.log(`[Daemon] Agent pipeline attempt ${attempt + 1} failed, retrying in ${RETRY_DELAY_MS}ms...`);
          await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        } else {
          throw error;
        }
      }
    }
  }

  private executeAgentPipeline(): Promise<void> {
    const agentPath = path.join(this.cognitiveSensorDir, 'run_agents.py');

    if (!fs.existsSync(agentPath)) {
      throw new Error(`run_agents.py not found at: ${agentPath}`);
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this.agentProcess) {
          this.agentProcess.kill();
          this.agentProcess = null;
        }
        reject(new Error(`Agent pipeline timed out after ${this.AGENT_PIPELINE_TIMEOUT_MS}ms`));
      }, this.AGENT_PIPELINE_TIMEOUT_MS);

      this.agentProcess = spawn('python', [agentPath], {
        cwd: path.dirname(agentPath),
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      this.agentProcess.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      this.agentProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      this.agentProcess.on('close', async (code) => {
        clearTimeout(timeout);
        this.agentProcess = null;

        if (code === 0) {
          await this.updateSystemState({
            'daemon.last_agent_pipeline': now(),
            'daemon.agent_pipeline_output': stdout.slice(-500),
          });

          this.timeline.emit('AGENT_PIPELINE_COMPLETE', 'governance_daemon', {
            output_length: stdout.length,
          });

          resolve();
        } else {
          reject(new Error(`run_agents.py exited with code ${code}: ${stderr}`));
        }
      });

      this.agentProcess.on('error', (err) => {
        clearTimeout(timeout);
        this.agentProcess = null;
        reject(err);
      });
    });
  }

  /**
   * Phase 4A: Auto-promote top ideas to tasks.
   * Reads idea_registry.json, finds execute_now ideas with score >= 0.80,
   * creates task entities. Max 3 per run.
   */
  private async autoPromoteIdeas(): Promise<void> {
    const registryPath = path.join(this.cognitiveSensorDir, 'idea_registry.json');
    if (!fs.existsSync(registryPath)) return;

    try {
      const registry = JSON.parse(fs.readFileSync(registryPath, 'utf-8'));
      const ideas: Array<{ title?: string; name?: string; tier?: string; priority_score?: number; id?: string }> =
        registry.ideas || registry.entries || [];

      const executeNow = ideas
        .filter(i => i.tier === 'execute_now' && (i.priority_score ?? 0) >= 0.80)
        .slice(0, 3);

      if (executeNow.length === 0) return;

      // Check existing tasks to avoid duplicates
      const existingTasks = this.storage.loadEntitiesByType<Record<string, unknown>>('task');
      const existingTitles = new Set(existingTasks.map(t => (t.state.title as string || '').toLowerCase()));

      let promoted = 0;
      for (const idea of executeNow) {
        const title = idea.title || idea.name || 'Untitled idea';
        if (existingTitles.has(title.toLowerCase())) continue;

        const result = await createEntity('task', {
          title_template: title,
          title_params: {},
          status: 'OPEN',
          priority: 'HIGH',
          due_at: null,
          linked_thread: null,
          source: 'idea_auto_promote',
          source_id: idea.id || null,
          source_score: idea.priority_score,
          created_at: now(),
        } as any);
        this.storage.saveEntity(result.entity, result.state);
        this.storage.appendDelta(result.delta);
        promoted++;

        this.timeline.emit('IDEA_AUTO_PROMOTED', 'governance_daemon', {
          title,
          score: idea.priority_score,
          entity_id: result.entity.entity_id,
        });
      }

      if (promoted > 0) {
        console.log(`[Daemon] Auto-promoted ${promoted} idea(s) to tasks`);
      }
    } catch (e) {
      console.error('[Daemon] Auto-promote ideas failed:', (e as Error).message);
    }
  }

  /**
   * Preparation: Run the preparation engine every 5 minutes.
   * Stores results as a preparation_result entity for the API to serve.
   */
  private async runPreparation(): Promise<void> {
    // Load system state
    const systemEntities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');
    if (systemEntities.length === 0) return;

    const systemState = systemEntities[0];

    // Load threads, tasks, existing drafts
    const threads = this.storage.loadEntitiesByType<Record<string, unknown>>('thread');
    const tasks = this.storage.loadEntitiesByType<Record<string, unknown>>('task');
    const drafts = this.storage.loadEntitiesByType<Record<string, unknown>>('draft');

    try {
      // Dynamic import to avoid circular deps at module level
      const { runPreparationEngine } = await import('../core/preparation.js');

      const result = await runPreparationEngine({
        systemState: systemState as any,
        threads: threads as any,
        tasks: tasks as any,
        existingDrafts: drafts as any,
        triggeredByDeltaId: `daemon-prep-${now()}`,
      });

      // Save new drafts
      for (const draft of result.newDrafts) {
        this.storage.saveEntity(draft.entity, draft.state);
        this.storage.appendDelta(draft.delta);
      }

      // Store preparation result for API consumption
      const prepData = {
        threadTriage: result.threadTriage,
        taskTriage: result.taskTriage,
        leverageMoves: result.leverageMoves,
        drafts_generated: result.newDrafts.length,
        jobs: result.jobs,
        computed_at: now(),
      };

      const existingPrep = this.storage.loadEntitiesByType<Record<string, unknown>>('preparation_result');
      if (existingPrep.length > 0) {
        const existing = existingPrep[0];
        const delta = await createDelta(
          existing.entity,
          existing.state,
          Object.entries(prepData).map(([key, value]) => ({
            op: 'replace' as const,
            path: `/${key}`,
            value,
          })),
          'preparation_engine'
        );
        this.storage.saveEntity(delta.entity, delta.state);
        this.storage.appendDelta(delta.delta);
      } else {
        const entity = await createEntity('preparation_result', prepData);
        this.storage.saveEntity(entity.entity, entity.state);
        this.storage.appendDelta(entity.delta);
      }

      await this.updateSystemState({
        'daemon.last_preparation': now(),
        'daemon.preparation_drafts': result.newDrafts.length,
      });
    } catch (e) {
      console.error('[Daemon] Preparation engine failed:', (e as Error).message);
    }
  }

  /**
   * Phase 4B: Stall Detection — runs daily at 21:00.
   * - Tasks open > 3 days → emit TASK_STALLED event
   * - Tasks open > 7 days → auto-archive
   * - Ideas in execute_now > 14 days without task → demote to next_up
   */
  private async runStallCheck(): Promise<void> {
    const nowMs = now();
    const THREE_DAYS = 3 * 24 * 60 * 60 * 1000;
    const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000;

    const tasks = this.storage.loadEntitiesByType<Record<string, unknown>>('task');
    let stalledCount = 0;
    let archivedCount = 0;

    for (const task of tasks) {
      const status = task.state.status as string;
      if (status === 'DONE' || status === 'ARCHIVED') continue;

      const createdAt = (task.state.created_at as number) || 0;
      const age = nowMs - createdAt;

      if (age > SEVEN_DAYS) {
        // Auto-archive stale tasks
        task.state.status = 'ARCHIVED';
        task.state.archived_reason = 'stall_auto_archive';
        task.state.archived_at = nowMs;
        this.storage.saveEntity(task.entity, task.state);
        archivedCount++;

        this.timeline.emit('TASK_AUTO_ARCHIVED', 'governance_daemon', {
          entity_id: task.entity.entity_id,
          title: task.state.title,
          age_days: Math.round(age / (24 * 60 * 60 * 1000)),
        });
      } else if (age > THREE_DAYS) {
        stalledCount++;
        this.timeline.emit('TASK_STALLED', 'governance_daemon', {
          entity_id: task.entity.entity_id,
          title: task.state.title,
          age_days: Math.round(age / (24 * 60 * 60 * 1000)),
        });
      }
    }

    await this.updateSystemState({
      'daemon.last_stall_check': nowMs,
      'daemon.stalled_tasks': stalledCount,
      'daemon.auto_archived_tasks': archivedCount,
    });

    if (stalledCount > 0 || archivedCount > 0) {
      console.log(`[Daemon] Stall check: ${stalledCount} stalled, ${archivedCount} auto-archived`);
    }
  }

  /**
   * Sensor Daily: run cognitive-sensor's run_daily.py once a day, ahead of
   * Day Start. This is the front of the spine that ATLAS_HEADLESS_MAP.md
   * flagged as unscheduled — without it, Optogon/cortex reason over stale or
   * empty input. Non-critical by design: a failure here logs and moves on,
   * it never blocks Day Start or seeding.
   */
  private async runSensorDaily(): Promise<void> {
    const scriptPath = path.join(this.cognitiveSensorDir, 'run_daily.py');

    if (!fs.existsSync(scriptPath)) {
      throw new Error(`run_daily.py not found at: ${scriptPath}`);
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this.sensorProcess) {
          this.sensorProcess.kill();
          this.sensorProcess = null;
        }
        reject(new Error(`Sensor daily pipeline timed out after ${this.SENSOR_DAILY_TIMEOUT_MS}ms`));
      }, this.SENSOR_DAILY_TIMEOUT_MS);

      this.sensorProcess = spawn('python', [scriptPath], {
        cwd: this.cognitiveSensorDir,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      this.sensorProcess.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      this.sensorProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      this.sensorProcess.on('close', async (code) => {
        clearTimeout(timeout);
        this.sensorProcess = null;

        if (code === 0) {
          await this.updateSystemState({
            'daemon.last_sensor_daily': now(),
            'daemon.sensor_daily_output': stdout.slice(-500),
          });
          this.timeline.emit('SENSOR_DAILY_COMPLETE', 'governance_daemon', {
            output_length: stdout.length,
          });
          resolve();
        } else {
          reject(new Error(`run_daily.py exited with code ${code}: ${stderr.slice(-500)}`));
        }
      });

      this.sensorProcess.on('error', (err) => {
        clearTimeout(timeout);
        this.sensorProcess = null;
        reject(err);
      });
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
    const cognitiveStatePath = path.join(this.cognitiveSensorDir, 'cognitive_state.json');
    const closuresPath = path.join(this.cognitiveSensorDir, 'closures.json');

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

    // Read current system_state for existing signals + mode
    const entities = this.storage.loadEntitiesByType<Record<string, unknown>>('system_state');
    const currentState = entities.length > 0 ? entities[0].state : {};
    const previousMode = ((currentState as Record<string, unknown>).mode as Mode) || 'CLOSURE';

    // Build signals from system_state, override open_loops with fresh cognitive data
    const existingSignals = (currentState as Record<string, unknown>).signals as SystemStateData['signals'] | undefined;
    const signals: SystemStateData['signals'] = {
      sleep_hours: existingSignals?.sleep_hours ?? 7,
      open_loops: openLoops,
      assets_shipped: existingSignals?.assets_shipped ?? 0,
      deep_work_blocks: existingSignals?.deep_work_blocks ?? 0,
      money_delta: existingSignals?.money_delta ?? 0,
    };

    // Use canonical routing.ts — same rules as API
    const newMode = route(previousMode, signals);
    const buildAllowed = newMode === 'BUILD' || newMode === 'COMPOUND' || newMode === 'SCALE';
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

      // Emit to NATS event bus for real-time UI push
      emitEvent('mode.changed', {
        oldMode: previousMode,
        newMode,
        closureRatio,
        openLoops,
        buildAllowed,
        reason: `Autonomous recalc: ratio=${closureRatio.toFixed(2)}`,
      }).catch(() => {}); // Best-effort — don't block on NATS

      // Push to phone — best-effort, never block the daemon loop
      notifyPhone('Mode Changed', `${previousMode} → ${newMode} (ratio=${closureRatio.toFixed(2)})`).catch(() => {});

      // Re-run preparation engine immediately on mode change
      // so Command screen shows actions relevant to the new mode
      try {
        await this.runPreparation();
        this.timeline.emit('MODE_TRANSITION_ACTIONS', 'governance_daemon', {
          previous_mode: previousMode,
          new_mode: newMode,
        });
      } catch (e) {
        console.error('[Daemon] Mode transition preparation failed:', (e as Error).message);
      }
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
      const stateData: SystemStateData = {
        mode: (expandedFields.mode as SystemStateData['mode']) || 'RECOVER',
        signals: (expandedFields.signals as SystemStateData['signals']) || {
          sleep_hours: 6, open_loops: 0, assets_shipped: 0, deep_work_blocks: 0, money_delta: 0,
        },
        ...expandedFields,
      };
      const result = await createEntity('system_state', stateData);
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
      case 'agent_pipeline':
        this.state.last_agent_pipeline = timestamp;
        break;
      case 'preparation':
        this.state.last_preparation = timestamp;
        break;
      case 'stall_check':
        this.state.last_stall_check = timestamp;
        break;
      case 'sensor_daily':
        this.state.last_sensor_daily = timestamp;
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
