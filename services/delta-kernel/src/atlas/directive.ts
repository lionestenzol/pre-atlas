/**
 * Atlas Directive Emitter - Phase 3A of doctrine/04_BUILD_PLAN.md.
 *
 * Transforms WorkLedger active/queued jobs into Directive.v1.json shape
 * (contracts/schemas/Directive.v1.json). Validates against the schema
 * on every emit; refuses to return an invalid Directive.
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import Ajv, { type ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import type { ActiveJob, QueuedJob, WorkLedger } from '../core/work-controller.js';

// === Directive shape (mirrors contracts/schemas/Directive.v1.json) =========
export interface DirectiveTask {
  id: string;
  label: string;
  description?: string;
  type: 'build' | 'fix' | 'research' | 'review' | 'deploy' | 'configure';
  estimated_complexity?: 'trivial' | 'simple' | 'moderate' | 'complex';
  success_criteria: string[];
  constraints?: string[];
}

export interface RelevantDecision {
  key: string;
  value?: unknown;
  source: string;
  made_at?: string;
}

export interface ContextBundle {
  project_id: string;
  relevant_files?: string[];
  relevant_decisions?: RelevantDecision[];
  user_preferences?: Record<string, unknown>;
  prior_attempts?: Array<{ attempt_id: string; outcome: string; lessons?: string[] }>;
  site_pull_context_id?: string | null;
}

export interface ExecutionSpec {
  target_path_id?: string | null;
  target_agent: 'claude_code' | 'optogon' | 'human';
  autonomy_level: 'full' | 'supervised' | 'approval_required';
  timeout_seconds?: number;
  fallback?: 'escalate_to_human' | 'retry' | 'skip';
}

export interface InterruptPolicy {
  interruptible: boolean;
  interrupt_threshold?: 'critical_only' | 'high_and_above' | 'any';
  resume_on_interrupt?: boolean;
}

export interface Directive {
  schema_version: '1.0';
  id: string;
  issued_at: string;
  priority_tier: 'critical' | 'high' | 'medium' | 'low';
  leverage_score: number;
  task: DirectiveTask;
  context_bundle: ContextBundle;
  execution: ExecutionSpec;
  interrupt_policy: InterruptPolicy;
}

export interface UnifiedStateSnapshot {
  delta_state?: Record<string, unknown>;
  cognitive_state?: Record<string, unknown>;
  work_ledger?: WorkLedger;
  primary_order?: string[];
  user_preferences?: Record<string, unknown>;
  leverage_score?: number;
}

// === Validator (ajv, cached) ===============================================
let cachedValidator: ValidateFunction | null = null;

function getValidator(repoRoot: string): ValidateFunction {
  if (cachedValidator) return cachedValidator;
  const schemaPath = join(repoRoot, 'contracts', 'schemas', 'Directive.v1.json');
  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  cachedValidator = ajv.compile(schema);
  return cachedValidator;
}

// === Helpers ===============================================================
function generateId(): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `dir_${Date.now().toString(36)}_${rand}`;
}

function leverageToPriority(score: number): Directive['priority_tier'] {
  if (score >= 0.75) return 'critical';
  if (score >= 0.5) return 'high';
  if (score >= 0.25) return 'medium';
  return 'low';
}

function coerceTaskType(value: unknown): DirectiveTask['type'] {
  const allowed: DirectiveTask['type'][] = ['build', 'fix', 'research', 'review', 'deploy', 'configure'];
  return (typeof value === 'string' && (allowed as string[]).includes(value)) ? (value as DirectiveTask['type']) : 'build';
}

function coerceStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const filtered = value.filter((v): v is string => typeof v === 'string');
  return filtered.length ? filtered : undefined;
}

function jobToTask(job: ActiveJob | QueuedJob): DirectiveTask {
  const meta = (job.metadata || {}) as Record<string, unknown>;
  return {
    id: job.job_id,
    label: job.title,
    description: typeof meta.description === 'string' ? meta.description : undefined,
    type: coerceTaskType(meta.task_type),
    estimated_complexity: typeof meta.complexity === 'string'
      ? (meta.complexity as DirectiveTask['estimated_complexity'])
      : undefined,
    success_criteria: coerceStringArray(meta.success_criteria) ?? [`Complete: ${job.title}`],
    constraints: coerceStringArray(meta.constraints),
  };
}

function buildContextBundle(snapshot: UnifiedStateSnapshot, job: ActiveJob | QueuedJob): ContextBundle {
  const meta = (job.metadata || {}) as Record<string, unknown>;
  return {
    project_id: 'pre-atlas',
    relevant_files: coerceStringArray(meta.relevant_files),
    relevant_decisions: Array.isArray(meta.relevant_decisions)
      ? (meta.relevant_decisions as RelevantDecision[])
      : undefined,
    user_preferences: snapshot.user_preferences,
    prior_attempts: Array.isArray(meta.prior_attempts)
      ? (meta.prior_attempts as ContextBundle['prior_attempts'])
      : undefined,
    site_pull_context_id: typeof meta.site_pull_context_id === 'string' ? meta.site_pull_context_id : null,
  };
}

// === Emitter ===============================================================
export class DirectiveEmitter {
  private readonly repoRoot: string;

  constructor(repoRoot: string) {
    this.repoRoot = repoRoot;
  }

  /** Emit the next Directive from the snapshot. Returns null if no candidate job. */
  emit(snapshot: UnifiedStateSnapshot): Directive | null {
    const ledger = snapshot.work_ledger;
    const job: ActiveJob | QueuedJob | undefined = ledger?.active?.[0] ?? ledger?.queued?.[0];
    if (!job) return null;

    const meta = (job.metadata || {}) as Record<string, unknown>;
    const leverageScore = typeof snapshot.leverage_score === 'number'
      ? Math.min(Math.max(snapshot.leverage_score, 0), 1)
      : 0.5;

    const directive: Directive = {
      schema_version: '1.0',
      id: generateId(),
      issued_at: new Date().toISOString(),
      priority_tier: leverageToPriority(leverageScore),
      leverage_score: leverageScore,
      task: jobToTask(job),
      context_bundle: buildContextBundle(snapshot, job),
      execution: {
        target_path_id: typeof meta.target_path_id === 'string' ? meta.target_path_id : null,
        target_agent: (typeof meta.target_agent === 'string'
          ? (meta.target_agent as ExecutionSpec['target_agent'])
          : 'optogon'),
        autonomy_level: (typeof meta.autonomy_level === 'string'
          ? (meta.autonomy_level as ExecutionSpec['autonomy_level'])
          : 'supervised'),
        timeout_seconds: 'timeout_ms' in job && typeof job.timeout_ms === 'number'
          ? Math.floor(job.timeout_ms / 1000)
          : undefined,
        fallback: (typeof meta.fallback === 'string'
          ? (meta.fallback as ExecutionSpec['fallback'])
          : 'escalate_to_human'),
      },
      interrupt_policy: {
        interruptible: typeof meta.interruptible === 'boolean' ? meta.interruptible : true,
        interrupt_threshold: (typeof meta.interrupt_threshold === 'string'
          ? (meta.interrupt_threshold as InterruptPolicy['interrupt_threshold'])
          : 'high_and_above'),
        resume_on_interrupt: typeof meta.resume_on_interrupt === 'boolean' ? meta.resume_on_interrupt : true,
      },
    };

    this.validateOrThrow(directive);
    return directive;
  }

  /** Validate payload against Directive.v1.json. Throws on failure. */
  private validateOrThrow(directive: Directive): void {
    const validate = getValidator(this.repoRoot);
    const ok = validate(directive);
    if (!ok) {
      const messages = (validate.errors || []).map((e) => `${e.instancePath || '<root>'}: ${e.message}`);
      throw new DirectiveValidationError('Directive failed schema validation', messages);
    }
  }
}

export class DirectiveValidationError extends Error {
  readonly details: string[];
  constructor(message: string, details: string[]) {
    super(`${message}: ${details.join('; ')}`);
    this.name = 'DirectiveValidationError';
    this.details = details;
  }
}

/** Express handler helper. Returns null if no candidate directive. */
export async function handleNextDirectiveRequest(
  repoRoot: string,
  snapshot: UnifiedStateSnapshot
): Promise<Directive | null> {
  const emitter = new DirectiveEmitter(repoRoot);
  return emitter.emit(snapshot);
}
