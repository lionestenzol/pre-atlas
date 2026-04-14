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
import { Mode, SystemStateData, ActionType } from '../core/types';
import { WorkController } from '../core/work-controller';
import { getTimelineLogger, TimelineLogger } from '../core/timeline-logger.js';
import { getEffectiveRiskTier } from '../core/cockpit.js';
import { emitEvent } from '../core/event-emitter.js';

// === TYPES ===

export type JobName = 'heartbeat' | 'refresh' | 'day_start' | 'day_end' | 'mode_recalc' | 'work_queue' | 'agent_pipeline' | 'preparation' | 'stall_check';

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
  private readonly REFRESH_TIMEOUT_MS = 120000;       // 2 minutes
  private readonly AGENT_PIPELINE_TIMEOUT_MS = 600000; // 10 minutes

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

    // Schedule agent pipeline (weekly Sunday 06:00)
    const agentPipelineJob = cron.schedule(this.AGENT_PIPELINE_CRON, () => {
      this.runJob('agent_pipeline');
    });
    this.cronJobs.push(agentPipelineJob);

    // Schedule preparation engine (every 5 minutes)
    const preparationJob = cron.schedule(this.PREPARATION_CRON, () => {
      this.runJob('preparation');
    });
    this.cronJobs.push(preparationJob);

    // Schedule stall detection (21:00 daily)
    const stallCheckJob = cron.schedule(this.STALL_CHECK_CRON, () => {
      this.runJob('stall_check');
    });
    this.cronJobs.push(stallCheckJob);

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
