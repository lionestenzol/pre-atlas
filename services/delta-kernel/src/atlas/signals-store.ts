/**
 * Signals store - in-memory ring buffer for Signal.v1 payloads from all layers.
 *
 * Phase 3c of doctrine/04_BUILD_PLAN.md. Signals are ephemeral by design:
 * they either get acted on (approval_required, error) or logged and forgotten
 * (status, completion). Delta-kernel does not persist them.
 *
 * Validates every ingested signal against Signal.v1.json before accepting.
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import Ajv, { type ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';

export interface Signal {
  schema_version: '1.0';
  id: string;
  emitted_at: string;
  source_layer: 'site_pull' | 'optogon' | 'atlas' | 'ghost_executor' | 'claude_code';
  signal_type: 'status' | 'completion' | 'blocked' | 'approval_required' | 'error' | 'insight';
  priority: 'urgent' | 'normal' | 'low';
  payload: {
    task_id?: string | null;
    label: string;
    summary: string;
    data?: Record<string, unknown>;
    action_required?: boolean;
    action_options?: Array<{
      id: string;
      label: string;
      consequence?: string;
      risk_tier: 'low' | 'medium' | 'high';
    }>;
  };
}

export interface SignalResolution {
  signal_id: string;
  action_id: string;
  resolved_at: string;
}

const MAX_SIGNALS = 500;

let cachedValidator: ValidateFunction | null = null;
const signals: Signal[] = [];
const resolutions: SignalResolution[] = [];

function getValidator(repoRoot: string): ValidateFunction {
  if (cachedValidator) return cachedValidator;
  const schemaPath = join(repoRoot, 'contracts', 'schemas', 'Signal.v1.json');
  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  cachedValidator = ajv.compile(schema);
  return cachedValidator;
}

export class SignalValidationError extends Error {
  readonly details: string[];
  constructor(message: string, details: string[]) {
    super(`${message}: ${details.join('; ')}`);
    this.name = 'SignalValidationError';
    this.details = details;
  }
}

/** Ingest a signal. Throws SignalValidationError on schema failure. */
export function ingestSignal(repoRoot: string, payload: unknown): Signal {
  const validate = getValidator(repoRoot);
  const ok = validate(payload);
  if (!ok) {
    const messages = (validate.errors || []).map((e) => `${e.instancePath || '<root>'}: ${e.message}`);
    throw new SignalValidationError('Signal failed schema validation', messages);
  }
  const signal = payload as Signal;
  signals.push(signal);
  if (signals.length > MAX_SIGNALS) {
    signals.splice(0, signals.length - MAX_SIGNALS);
  }
  return signal;
}

/** List signals, newest first. Optional ?since=timestamp filter. */
export function listSignals(since?: string): Signal[] {
  const filtered = since ? signals.filter((s) => s.emitted_at > since) : [...signals];
  // Return newest first so UI just takes slice(0, N)
  return filtered.reverse();
}

/** Record resolution of an approval_required signal. Returns null if not found. */
export function resolveSignal(signalId: string, actionId: string): SignalResolution | null {
  const idx = signals.findIndex((s) => s.id === signalId);
  if (idx === -1) return null;
  const resolution: SignalResolution = {
    signal_id: signalId,
    action_id: actionId,
    resolved_at: new Date().toISOString(),
  };
  resolutions.push(resolution);
  // Remove the resolved signal from the active list
  signals.splice(idx, 1);
  return resolution;
}

export function listResolutions(): SignalResolution[] {
  return [...resolutions];
}

export function clearAll(): void {
  signals.length = 0;
  resolutions.length = 0;
}
