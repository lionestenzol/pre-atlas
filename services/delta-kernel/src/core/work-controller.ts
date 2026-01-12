/**
 * Work Admission Controller — Phase 6A
 *
 * Universal work controller for humans AND machines.
 * All work passes through a single admission gate.
 *
 * Three Primitives:
 * 1. request() — Ask permission to start a job
 * 2. complete() — Report job completion
 * 3. status() — Query current work state
 */

import * as fs from 'fs';
import * as path from 'path';
import { getTimelineLogger, TimelineLogger } from './timeline-logger.js';

// === TYPES ===

export type JobType = 'human' | 'ai' | 'system';
export type JobOutcome = 'completed' | 'failed' | 'abandoned';
export type AdmissionStatus = 'APPROVED' | 'QUEUED' | 'DENIED';

export interface ActiveJob {
  job_id: string;
  type: JobType;
  title: string;
  agent?: string;
  weight: number;
  started_at: number;
  timeout_at: number | null;
  depends_on: string[];
  metadata: Record<string, unknown>;
}

export interface QueuedJob {
  job_id: string;
  type: JobType;
  title: string;
  agent?: string;
  weight: number;
  queued_at: number;
  depends_on: string[];
  position: number;
  reason: string;
  blocked_by: string[];
  metadata: Record<string, unknown>;
}

export interface CompletedJob {
  job_id: string;
  type: JobType;
  title: string;
  agent?: string;
  outcome: JobOutcome;
  started_at: number;
  completed_at: number;
  duration_ms: number;
  error: string | null;
  metrics: {
    tokens_used?: number;
    cost_usd?: number;
  };
  metadata: Record<string, unknown>;
}

export interface WorkLedgerConfig {
  max_concurrent_jobs: number;
  max_queue_depth: number;
  default_timeout_ms: number;
  allow_ai_in_closure_mode: boolean;
}

export interface WorkLedger {
  active: ActiveJob[];
  queued: QueuedJob[];
  completed: CompletedJob[];
  stats: {
    total_completed: number;
    total_failed: number;
    total_abandoned: number;
    total_denied: number;
    avg_duration_ms: number;
    total_cost_usd: number;
    total_tokens_used: number;
  };
  config: WorkLedgerConfig;
}

export interface WorkRequest {
  job_id?: string;
  type: JobType;
  title: string;
  agent?: string;
  weight?: number;
  depends_on?: string[];
  timeout_ms?: number;
  metadata?: Record<string, unknown>;
}

export interface ApprovedResponse {
  status: 'APPROVED';
  job_id: string;
  started_at: number;
  expires_at: number | null;
  slot: number;
  total_slots: number;
}

export interface QueuedResponse {
  status: 'QUEUED';
  job_id: string;
  position: number;
  queue_depth: number;
  reason: string;
  blocked_by: string[];
  estimated_wait_ms: number;
}

export interface DeniedResponse {
  status: 'DENIED';
  reason: string;
  required_action?: string;
  mode?: string;
  open_loops?: number;
  closure_ratio?: number;
}

export type AdmissionResponse = ApprovedResponse | QueuedResponse | DeniedResponse;

export interface CompleteRequest {
  job_id: string;
  outcome: JobOutcome;
  result?: unknown;
  error?: string;
  metrics?: {
    duration_ms?: number;
    tokens_used?: number;
    cost_usd?: number;
  };
}

export interface CompleteResponse {
  success: boolean;
  job_id: string;
  outcome: JobOutcome;
  completed_at: number;
  duration_ms: number;
  freed_slot: boolean;
  queue_advanced: boolean;
  next_job_started: string | null;
  closure_count: number;
  streak_days: number;
}

export interface WorkStatusResponse {
  capacity: {
    max_concurrent: number;
    active: number;
    available: number;
    queue_depth: number;
    max_queue: number;
  };
  active_jobs: Array<{
    job_id: string;
    type: JobType;
    title: string;
    agent?: string;
    started_at: number;
    elapsed_ms: number;
    timeout_ms: number | null;
  }>;
  queued_jobs: Array<{
    job_id: string;
    position: number;
    blocked_by: string[];
    queued_at: number;
  }>;
  mode: string;
  build_allowed: boolean;
  closure_ratio: number;
}

export interface CancelRequest {
  job_id: string;
  reason?: string;
}

export interface CancelResponse {
  success: boolean;
  job_id: string;
  was_active: boolean;
  freed_slot: boolean;
  queue_advanced: boolean;
}

// === WORK CONTROLLER ===

export class WorkController {
  private ledgerPath: string;
  private ledger: WorkLedger;
  private timeline: TimelineLogger;
  private repoRoot: string;

  constructor(repoRoot: string) {
    this.repoRoot = repoRoot;
    this.ledgerPath = path.join(repoRoot, 'services/cognitive-sensor/work_ledger.json');
    this.ledger = this.loadLedger();
    this.timeline = getTimelineLogger(repoRoot);
  }

  private loadLedger(): WorkLedger {
    try {
      if (fs.existsSync(this.ledgerPath)) {
        return JSON.parse(fs.readFileSync(this.ledgerPath, 'utf-8'));
      }
    } catch (e) {
      console.error('[WorkController] Failed to load ledger:', (e as Error).message);
    }

    // Return default ledger
    return {
      active: [],
      queued: [],
      completed: [],
      stats: {
        total_completed: 0,
        total_failed: 0,
        total_abandoned: 0,
        total_denied: 0,
        avg_duration_ms: 0,
        total_cost_usd: 0,
        total_tokens_used: 0,
      },
      config: {
        max_concurrent_jobs: 1,
        max_queue_depth: 5,
        default_timeout_ms: 600000,
        allow_ai_in_closure_mode: false,
      },
    };
  }

  private saveLedger(): void {
    try {
      const dir = path.dirname(this.ledgerPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.ledgerPath, JSON.stringify(this.ledger, null, 2));
    } catch (e) {
      console.error('[WorkController] Failed to save ledger:', (e as Error).message);
    }
  }

  private generateJobId(): string {
    return 'j_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  private getActiveSlots(): number {
    // Sum weights of active jobs
    return this.ledger.active.reduce((sum, job) => sum + job.weight, 0);
  }

  private getUnmetDependencies(depends_on: string[]): string[] {
    if (!depends_on || depends_on.length === 0) return [];

    const completedIds = new Set(
      this.ledger.completed
        .filter(j => j.outcome === 'completed')
        .map(j => j.job_id)
    );

    return depends_on.filter(dep => !completedIds.has(dep));
  }

  /**
   * Request permission to start a job.
   * Returns APPROVED, QUEUED, or DENIED.
   */
  request(
    req: WorkRequest,
    systemState: { mode: string; build_allowed: boolean; open_loops?: number; closure_ratio?: number }
  ): AdmissionResponse {
    const timestamp = Date.now();
    const job_id = req.job_id || this.generateJobId();
    const weight = req.weight || 1;
    const depends_on = req.depends_on || [];
    const timeout_ms = req.timeout_ms || this.ledger.config.default_timeout_ms;

    // Emit WORK_REQUESTED event
    this.timeline.emit('WORK_REQUESTED', 'work_controller', {
      job_id,
      type: req.type,
      title: req.title,
      agent: req.agent,
    });

    // === ADMISSION CHECK 1: MODE ===
    // In CLOSURE mode, deny AI work unless explicitly allowed
    if (systemState.mode === 'CLOSURE') {
      if (req.type === 'ai' && !this.ledger.config.allow_ai_in_closure_mode) {
        this.ledger.stats.total_denied++;
        this.saveLedger();
        this.timeline.emit('WORK_DENIED', 'work_controller', {
          job_id,
          reason: 'AI work blocked in CLOSURE mode',
          mode: systemState.mode,
        });
        return {
          status: 'DENIED',
          reason: 'AI work blocked in CLOSURE mode',
          required_action: 'Close or archive open loops first',
          mode: systemState.mode,
          open_loops: systemState.open_loops,
          closure_ratio: systemState.closure_ratio,
        };
      }
    }

    // If build not allowed and this isn't system/closure work, deny
    if (!systemState.build_allowed && req.type !== 'system') {
      this.ledger.stats.total_denied++;
      this.saveLedger();
      this.timeline.emit('WORK_DENIED', 'work_controller', {
        job_id,
        reason: 'Must close loops first',
        mode: systemState.mode,
      });
      return {
        status: 'DENIED',
        reason: 'Must close loops first',
        required_action: 'Close or archive open loops',
        mode: systemState.mode,
        open_loops: systemState.open_loops,
        closure_ratio: systemState.closure_ratio,
      };
    }

    // === ADMISSION CHECK 2: DEPENDENCIES ===
    const blockedBy = this.getUnmetDependencies(depends_on);
    if (blockedBy.length > 0) {
      // Queue with dependency block
      const position = this.ledger.queued.length + 1;

      const queuedJob: QueuedJob = {
        job_id,
        type: req.type,
        title: req.title,
        agent: req.agent,
        weight,
        queued_at: timestamp,
        depends_on,
        position,
        reason: 'Waiting on dependencies',
        blocked_by: blockedBy,
        metadata: req.metadata || {},
      };

      this.ledger.queued.push(queuedJob);
      this.saveLedger();
      this.timeline.emit('WORK_QUEUED', 'work_controller', {
        job_id,
        position,
        reason: 'Waiting on dependencies',
        blocked_by: blockedBy,
      });

      return {
        status: 'QUEUED',
        job_id,
        position,
        queue_depth: this.ledger.queued.length,
        reason: 'Waiting on dependencies',
        blocked_by: blockedBy,
        estimated_wait_ms: 0, // Unknown when dependencies complete
      };
    }

    // === ADMISSION CHECK 3: CAPACITY ===
    const activeSlots = this.getActiveSlots();
    const maxSlots = this.ledger.config.max_concurrent_jobs;

    if (activeSlots + weight > maxSlots) {
      // At capacity — try to queue
      if (this.ledger.queued.length >= this.ledger.config.max_queue_depth) {
        this.ledger.stats.total_denied++;
        this.saveLedger();
        this.timeline.emit('WORK_DENIED', 'work_controller', {
          job_id,
          reason: 'System at capacity',
        });
        return {
          status: 'DENIED',
          reason: 'System at capacity',
          required_action: 'Wait for active jobs to complete',
        };
      }

      // Queue the job
      const position = this.ledger.queued.length + 1;
      const avgDuration = this.ledger.stats.avg_duration_ms || 60000;
      const estimatedWait = avgDuration * position;

      const queuedJob: QueuedJob = {
        job_id,
        type: req.type,
        title: req.title,
        agent: req.agent,
        weight,
        queued_at: timestamp,
        depends_on,
        position,
        reason: 'At capacity',
        blocked_by: [],
        metadata: req.metadata || {},
      };

      this.ledger.queued.push(queuedJob);
      this.saveLedger();
      this.timeline.emit('WORK_QUEUED', 'work_controller', {
        job_id,
        position,
        reason: 'At capacity',
        estimated_wait_ms: estimatedWait,
      });

      return {
        status: 'QUEUED',
        job_id,
        position,
        queue_depth: this.ledger.queued.length,
        reason: 'At capacity',
        blocked_by: [],
        estimated_wait_ms: estimatedWait,
      };
    }

    // === APPROVED ===
    const activeJob: ActiveJob = {
      job_id,
      type: req.type,
      title: req.title,
      agent: req.agent,
      weight,
      started_at: timestamp,
      timeout_at: timeout_ms ? timestamp + timeout_ms : null,
      depends_on,
      metadata: req.metadata || {},
    };

    this.ledger.active.push(activeJob);
    this.saveLedger();
    this.timeline.emit('WORK_APPROVED', 'work_controller', {
      job_id,
      type: req.type,
      title: req.title,
      agent: req.agent,
      slot: this.ledger.active.length,
      total_slots: maxSlots,
    });

    return {
      status: 'APPROVED',
      job_id,
      started_at: timestamp,
      expires_at: activeJob.timeout_at,
      slot: this.ledger.active.length,
      total_slots: maxSlots,
    };
  }

  /**
   * Report job completion.
   * Frees slot, advances queue, updates stats.
   */
  complete(req: CompleteRequest): CompleteResponse | { error: string; status: number } {
    const timestamp = Date.now();

    // Find job in active or queued
    const activeIndex = this.ledger.active.findIndex(j => j.job_id === req.job_id);
    const queuedIndex = this.ledger.queued.findIndex(j => j.job_id === req.job_id);

    if (activeIndex === -1 && queuedIndex === -1) {
      return { error: 'Job not found', status: 404 };
    }

    let job: ActiveJob | QueuedJob;
    let started_at: number;
    let wasActive = false;

    if (activeIndex !== -1) {
      job = this.ledger.active[activeIndex];
      started_at = job.started_at;
      wasActive = true;
      // Remove from active
      this.ledger.active.splice(activeIndex, 1);
    } else {
      job = this.ledger.queued[queuedIndex];
      started_at = (job as QueuedJob).queued_at;
      // Remove from queued
      this.ledger.queued.splice(queuedIndex, 1);
      // Update positions
      this.ledger.queued.forEach((q, i) => { q.position = i + 1; });
    }

    const duration_ms = req.metrics?.duration_ms || (timestamp - started_at);

    // Build completed job record
    const completedJob: CompletedJob = {
      job_id: req.job_id,
      type: job.type,
      title: job.title,
      agent: job.agent,
      outcome: req.outcome,
      started_at,
      completed_at: timestamp,
      duration_ms,
      error: req.error || null,
      metrics: {
        tokens_used: req.metrics?.tokens_used,
        cost_usd: req.metrics?.cost_usd,
      },
      metadata: job.metadata,
    };

    // Add to completed (keep last 100)
    this.ledger.completed.push(completedJob);
    if (this.ledger.completed.length > 100) {
      this.ledger.completed = this.ledger.completed.slice(-100);
    }

    // Update stats and emit timeline event
    if (req.outcome === 'completed') {
      this.ledger.stats.total_completed++;
      this.timeline.emit('WORK_COMPLETED', 'work_controller', {
        job_id: req.job_id,
        type: job.type,
        title: job.title,
        duration_ms,
      });
    } else if (req.outcome === 'failed') {
      this.ledger.stats.total_failed++;
      this.timeline.emit('WORK_FAILED', 'work_controller', {
        job_id: req.job_id,
        type: job.type,
        title: job.title,
        error: req.error,
        duration_ms,
      });
    } else {
      this.ledger.stats.total_abandoned++;
      this.timeline.emit('WORK_ABANDONED', 'work_controller', {
        job_id: req.job_id,
        type: job.type,
        title: job.title,
        duration_ms,
      });
    }

    // Update average duration
    const completedWithDuration = this.ledger.completed.filter(j => j.duration_ms > 0);
    if (completedWithDuration.length > 0) {
      const totalDuration = completedWithDuration.reduce((sum, j) => sum + j.duration_ms, 0);
      this.ledger.stats.avg_duration_ms = Math.round(totalDuration / completedWithDuration.length);
    }

    // Update cost tracking
    if (req.metrics?.cost_usd) {
      this.ledger.stats.total_cost_usd += req.metrics.cost_usd;
    }
    if (req.metrics?.tokens_used) {
      this.ledger.stats.total_tokens_used += req.metrics.tokens_used;
    }

    // === ADVANCE QUEUE ===
    let nextJobStarted: string | null = null;
    let queueAdvanced = false;

    if (wasActive && this.ledger.queued.length > 0) {
      // Try to promote next eligible job
      for (let i = 0; i < this.ledger.queued.length; i++) {
        const candidate = this.ledger.queued[i];
        const blockedBy = this.getUnmetDependencies(candidate.depends_on);

        if (blockedBy.length === 0) {
          const activeSlots = this.getActiveSlots();
          if (activeSlots + candidate.weight <= this.ledger.config.max_concurrent_jobs) {
            // Promote to active
            const promotedJob: ActiveJob = {
              job_id: candidate.job_id,
              type: candidate.type,
              title: candidate.title,
              agent: candidate.agent,
              weight: candidate.weight,
              started_at: timestamp,
              timeout_at: timestamp + this.ledger.config.default_timeout_ms,
              depends_on: candidate.depends_on,
              metadata: candidate.metadata,
            };

            this.ledger.active.push(promotedJob);
            this.ledger.queued.splice(i, 1);
            // Update positions
            this.ledger.queued.forEach((q, idx) => { q.position = idx + 1; });

            // Emit event for promoted job
            this.timeline.emit('WORK_APPROVED', 'work_controller', {
              job_id: candidate.job_id,
              type: candidate.type,
              title: candidate.title,
              promoted_from_queue: true,
            });

            nextJobStarted = candidate.job_id;
            queueAdvanced = true;
            break;
          }
        }
      }
    }

    this.saveLedger();

    return {
      success: true,
      job_id: req.job_id,
      outcome: req.outcome,
      completed_at: timestamp,
      duration_ms,
      freed_slot: wasActive,
      queue_advanced: queueAdvanced,
      next_job_started: nextJobStarted,
      closure_count: this.ledger.stats.total_completed,
      streak_days: 0, // Caller should update from closures registry
    };
  }

  /**
   * Query current work state.
   */
  status(systemState: { mode: string; build_allowed: boolean; closure_ratio?: number }): WorkStatusResponse {
    const timestamp = Date.now();

    return {
      capacity: {
        max_concurrent: this.ledger.config.max_concurrent_jobs,
        active: this.ledger.active.length,
        available: Math.max(0, this.ledger.config.max_concurrent_jobs - this.getActiveSlots()),
        queue_depth: this.ledger.queued.length,
        max_queue: this.ledger.config.max_queue_depth,
      },
      active_jobs: this.ledger.active.map(job => ({
        job_id: job.job_id,
        type: job.type,
        title: job.title,
        agent: job.agent,
        started_at: job.started_at,
        elapsed_ms: timestamp - job.started_at,
        timeout_ms: job.timeout_at ? job.timeout_at - job.started_at : null,
      })),
      queued_jobs: this.ledger.queued.map(job => ({
        job_id: job.job_id,
        position: job.position,
        blocked_by: job.blocked_by,
        queued_at: job.queued_at,
      })),
      mode: systemState.mode,
      build_allowed: systemState.build_allowed,
      closure_ratio: systemState.closure_ratio || 0,
    };
  }

  /**
   * Cancel a job (active or queued).
   */
  cancel(req: CancelRequest): CancelResponse | { error: string; status: number } {
    const activeIndex = this.ledger.active.findIndex(j => j.job_id === req.job_id);
    const queuedIndex = this.ledger.queued.findIndex(j => j.job_id === req.job_id);

    if (activeIndex === -1 && queuedIndex === -1) {
      return { error: 'Job not found', status: 404 };
    }

    const wasActive = activeIndex !== -1;
    const cancelledJob = wasActive
      ? this.ledger.active[activeIndex]
      : this.ledger.queued[queuedIndex];

    if (wasActive) {
      // Remove from active
      this.ledger.active.splice(activeIndex, 1);
    } else {
      // Remove from queued
      this.ledger.queued.splice(queuedIndex, 1);
      // Update positions
      this.ledger.queued.forEach((q, i) => { q.position = i + 1; });
    }

    // Emit cancel event
    this.timeline.emit('WORK_CANCELLED', 'work_controller', {
      job_id: req.job_id,
      type: cancelledJob.type,
      title: cancelledJob.title,
      was_active: wasActive,
      reason: req.reason,
    });

    // Try to advance queue if we freed a slot
    let queueAdvanced = false;
    if (wasActive && this.ledger.queued.length > 0) {
      const timestamp = Date.now();
      for (let i = 0; i < this.ledger.queued.length; i++) {
        const candidate = this.ledger.queued[i];
        const blockedBy = this.getUnmetDependencies(candidate.depends_on);

        if (blockedBy.length === 0) {
          const activeSlots = this.getActiveSlots();
          if (activeSlots + candidate.weight <= this.ledger.config.max_concurrent_jobs) {
            // Promote to active
            const promotedJob: ActiveJob = {
              job_id: candidate.job_id,
              type: candidate.type,
              title: candidate.title,
              agent: candidate.agent,
              weight: candidate.weight,
              started_at: timestamp,
              timeout_at: timestamp + this.ledger.config.default_timeout_ms,
              depends_on: candidate.depends_on,
              metadata: candidate.metadata,
            };

            this.ledger.active.push(promotedJob);
            this.ledger.queued.splice(i, 1);
            this.ledger.queued.forEach((q, idx) => { q.position = idx + 1; });
            queueAdvanced = true;
            break;
          }
        }
      }
    }

    this.saveLedger();

    return {
      success: true,
      job_id: req.job_id,
      was_active: wasActive,
      freed_slot: wasActive,
      queue_advanced: queueAdvanced,
    };
  }

  /**
   * Check for timed-out jobs and advance queue.
   * Called by daemon on schedule.
   */
  checkTimeouts(): { timed_out: string[]; advanced: string[] } {
    const timestamp = Date.now();
    const timedOut: string[] = [];
    const advanced: string[] = [];

    // Find timed-out jobs
    const toTimeout = this.ledger.active.filter(
      job => job.timeout_at && job.timeout_at < timestamp
    );

    for (const job of toTimeout) {
      // Emit timeout event (before complete, which emits WORK_FAILED)
      this.timeline.emit('WORK_TIMEOUT', 'work_controller', {
        job_id: job.job_id,
        type: job.type,
        title: job.title,
        started_at: job.started_at,
        timeout_at: job.timeout_at,
      });

      // Complete as failed
      const result = this.complete({
        job_id: job.job_id,
        outcome: 'failed',
        error: 'Job timed out',
      });

      if ('success' in result && result.success) {
        timedOut.push(job.job_id);
        if (result.next_job_started) {
          advanced.push(result.next_job_started);
        }
      }
    }

    return { timed_out: timedOut, advanced };
  }

  /**
   * Get raw ledger for inspection.
   */
  getLedger(): WorkLedger {
    return { ...this.ledger };
  }
}
