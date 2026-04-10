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
import { emitEvent } from './event-emitter.js';

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
  timeout_ms: number | null;
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
  timeout_ms: number | null;
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
  result: unknown;
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
    work_claims_total: number;
    work_claims_failed_total: number;
    work_claims_extended_total: number;
    work_claims_expired_total: number;
    work_claim_ttl_ms_total: number;
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

export interface WorkClaimMetrics {
  totals: {
    claims: number;
    failed_claims: number;
    extended_claims: number;
    expired_claims: number;
  };
  active_claims: number;
  observed_expired_claims: number;
  average_claim_ttl_ms: number;
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

export interface ExecutableTaskClaim {
  claimed: boolean;
  executor_id: string;
  job: null | {
    job_id: string;
    type: JobType;
    title: string;
    agent?: string;
    started_at: number;
    timeout_at: number | null;
    metadata: Record<string, unknown>;
  };
}

export interface ExtendClaimResult {
  extended: boolean;
  job_id: string;
  executor_id: string;
  new_expires_at: number | null;
}

// === WORK CONTROLLER ===

export class WorkController {
  private ledgerPath: string;
  private ledger: WorkLedger;
  private timeline: TimelineLogger;
  private repoRoot: string;
  private readonly executionClaimTtlMs = 15 * 60 * 1000;
  private readonly minimumExecutionClaimTtlMs = 5 * 1000;

  constructor(repoRoot: string) {
    this.repoRoot = repoRoot;
    const cognitiveSensorDir = process.env.COGNITIVE_SENSOR_DIR || path.join(repoRoot, 'services', 'cognitive-sensor');
    this.ledgerPath = path.join(cognitiveSensorDir, 'work_ledger.json');
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
        work_claims_total: 0,
        work_claims_failed_total: 0,
        work_claims_extended_total: 0,
        work_claims_expired_total: 0,
        work_claim_ttl_ms_total: 0,
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

  private getExecutionClaim(metadata: Record<string, unknown> | undefined): Record<string, unknown> | null {
    if (!metadata || typeof metadata !== 'object') return null;
    const execution = metadata.execution;
    if (!execution || typeof execution !== 'object') return null;
    return execution as Record<string, unknown>;
  }

  private hasExecutableCommand(metadata: Record<string, unknown>): boolean {
    return typeof metadata.cmd === 'string' && metadata.cmd.trim().length > 0;
  }

  private getJobTimeoutMs(
    job: { timeout_ms?: number | null; started_at: number; timeout_at: number | null; metadata?: Record<string, unknown> }
  ): number | null {
    if (typeof job.timeout_ms === 'number' && job.timeout_ms > 0) {
      return job.timeout_ms;
    }

    if (typeof job.metadata?.timeout_ms === 'number' && job.metadata.timeout_ms > 0) {
      return job.metadata.timeout_ms as number;
    }

    if (typeof job.timeout_at === 'number' && job.timeout_at > job.started_at) {
      return job.timeout_at - job.started_at;
    }

    return null;
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
    const metadata = { ...(req.metadata || {}), timeout_ms };

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
        timeout_ms,
        depends_on,
        position,
        reason: 'Waiting on dependencies',
        blocked_by: blockedBy,
        metadata,
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
        timeout_ms,
        depends_on,
        position,
        reason: 'At capacity',
        blocked_by: [],
        metadata,
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
      timeout_ms,
      timeout_at: timeout_ms ? timestamp + timeout_ms : null,
      depends_on,
      metadata,
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
      result: req.result ?? null,
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
              timeout_ms: candidate.timeout_ms,
              timeout_at: candidate.timeout_ms ? timestamp + candidate.timeout_ms : null,
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

    // Emit task.completed to NATS event bus for real-time UI push
    emitEvent('task.completed', {
      jobId: req.job_id,
      outcome: req.outcome,
      durationMs: duration_ms,
      queueAdvanced,
      nextJobStarted: nextJobStarted,
    }).catch(() => {}); // Best-effort

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
   * Atomically claim the next approved executable task for autonomous execution.
   * Active jobs are considered approved. Only tasks with metadata.cmd are executable.
   */
  claimNextExecutable(executorId: string): ExecutableTaskClaim {
    const now = Date.now();

    for (const job of this.ledger.active) {
      if (!['ai', 'system'].includes(job.type)) continue;
      if (!this.hasExecutableCommand(job.metadata)) continue;

      const claim = this.getExecutionClaim(job.metadata);
      const claimExpiresAt = typeof claim?.claim_expires_at === 'number'
        ? claim.claim_expires_at as number
        : 0;

      if (claim && claimExpiresAt <= now && claim.claimed_by !== executorId && !claim.claim_expired_observed_at) {
        this.ledger.stats.work_claims_expired_total++;
        job.metadata.execution = {
          ...claim,
          claim_expired_observed_at: now,
        };
        this.timeline.emit('AUTO_EXECUTED', 'work_controller', {
          job_id: job.job_id,
          executor_id: executorId,
          claim_expired: true,
          previous_executor_id: claim.claimed_by,
          claim_expires_at: claimExpiresAt,
        });
      }

      if (claim && claimExpiresAt > now && claim.claimed_by !== executorId) {
        continue;
      }

      const previousAttempts = typeof claim?.attempts === 'number'
        ? claim.attempts as number
        : 0;
      const claimTtlMs = this.getJobTimeoutMs(job) ?? this.executionClaimTtlMs;
      const effectiveTtlMs = Math.max(claimTtlMs, this.minimumExecutionClaimTtlMs);

      job.metadata.execution = {
        claimed_by: executorId,
        claimed_at: now,
        claim_expires_at: now + effectiveTtlMs,
        attempts: previousAttempts + 1,
      };

      this.ledger.stats.work_claims_total++;
      this.ledger.stats.work_claim_ttl_ms_total += effectiveTtlMs;
      this.saveLedger();
      this.timeline.emit('AUTO_EXECUTED', 'work_controller', {
        job_id: job.job_id,
        executor_id: executorId,
        attempts: previousAttempts + 1,
        claim_ttl_ms: effectiveTtlMs,
        claim_expires_at: now + effectiveTtlMs,
      });

      return {
        claimed: true,
        executor_id: executorId,
        job: {
          job_id: job.job_id,
          type: job.type,
          title: job.title,
          agent: job.agent,
          started_at: job.started_at,
          timeout_at: job.timeout_at,
          metadata: { ...job.metadata },
        },
      };
    }

    this.ledger.stats.work_claims_failed_total++;
    this.saveLedger();

    return {
      claimed: false,
      executor_id: executorId,
      job: null,
    };
  }

  extendClaim(jobId: string, executorId: string, extensionMs?: number): ExtendClaimResult {
    const job = this.ledger.active.find(j => j.job_id === jobId);
    if (!job) {
      return { extended: false, job_id: jobId, executor_id: executorId, new_expires_at: null };
    }

    const claim = this.getExecutionClaim(job.metadata);
    if (!claim || claim.claimed_by !== executorId) {
      return { extended: false, job_id: jobId, executor_id: executorId, new_expires_at: null };
    }

    const baseTtlMs = extensionMs ?? this.getJobTimeoutMs(job) ?? this.executionClaimTtlMs;
    const effectiveTtlMs = Math.max(baseTtlMs, this.minimumExecutionClaimTtlMs);
    const newExpiresAt = Date.now() + effectiveTtlMs;

    job.metadata.execution = {
      ...claim,
      claimed_by: executorId,
      claim_expires_at: newExpiresAt,
      last_heartbeat_at: Date.now(),
    };

    this.ledger.stats.work_claims_extended_total++;
    this.ledger.stats.work_claim_ttl_ms_total += effectiveTtlMs;
    this.saveLedger();
    this.timeline.emit('AUTO_EXECUTED', 'work_controller', {
      job_id: job.job_id,
      executor_id: executorId,
      claim_extended: true,
      claim_ttl_ms: effectiveTtlMs,
      claim_expires_at: newExpiresAt,
    });

    return {
      extended: true,
      job_id: job.job_id,
      executor_id: executorId,
      new_expires_at: newExpiresAt,
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
              timeout_ms: candidate.timeout_ms,
              timeout_at: candidate.timeout_ms ? timestamp + candidate.timeout_ms : null,
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

  getClaimMetrics(): WorkClaimMetrics {
    const now = Date.now();
    const activeClaims = this.ledger.active.filter(job => {
      const claim = this.getExecutionClaim(job.metadata);
      return typeof claim?.claim_expires_at === 'number' && claim.claim_expires_at > now;
    }).length;

    const observedExpiredClaims = this.ledger.active.filter(job => {
      const claim = this.getExecutionClaim(job.metadata);
      return typeof claim?.claim_expires_at === 'number' && claim.claim_expires_at <= now;
    }).length;

    const successfulClaims = this.ledger.stats.work_claims_total + this.ledger.stats.work_claims_extended_total;

    return {
      totals: {
        claims: this.ledger.stats.work_claims_total,
        failed_claims: this.ledger.stats.work_claims_failed_total,
        extended_claims: this.ledger.stats.work_claims_extended_total,
        expired_claims: this.ledger.stats.work_claims_expired_total,
      },
      active_claims: activeClaims,
      observed_expired_claims: observedExpiredClaims,
      average_claim_ttl_ms: successfulClaims > 0
        ? Math.round(this.ledger.stats.work_claim_ttl_ms_total / successfulClaims)
        : 0,
    };
  }

  getJob(jobId: string): ActiveJob | QueuedJob | CompletedJob | null {
    return this.ledger.active.find(j => j.job_id === jobId)
      || this.ledger.queued.find(j => j.job_id === jobId)
      || this.ledger.completed.find(j => j.job_id === jobId)
      || null;
  }
}
