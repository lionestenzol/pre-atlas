/**
 * CloseSignal ingest handler. Per doctrine/02_ROSETTA_STONE.md Contract 2.
 *
 * Validates incoming CloseSignal, persists learned_preferences to the
 * preferences store, and returns a summary of what was recorded.
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import Ajv, { type ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import { PreferencesStore } from './preferences-store.js';

let cachedValidator: ValidateFunction | null = null;

function getValidator(repoRoot: string): ValidateFunction {
  if (cachedValidator) return cachedValidator;
  const schemaPath = join(repoRoot, 'contracts', 'schemas', 'CloseSignal.v1.json');
  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  cachedValidator = ajv.compile(schema);
  return cachedValidator;
}

export class CloseSignalValidationError extends Error {
  readonly details: string[];
  constructor(message: string, details: string[]) {
    super(`${message}: ${details.join('; ')}`);
    this.name = 'CloseSignalValidationError';
    this.details = details;
  }
}

export interface CloseSignalIngestResult {
  accepted: true;
  close_signal_id: string;
  path_id: string;
  status: string;
  preferences_written: number;
  decisions_count: number;
}

/**
 * Ingest a CloseSignal. Validates, persists preferences, returns summary.
 * @param userId usually the single-tenant user ID (e.g. "bruke").
 */
export function ingestCloseSignal(
  repoRoot: string,
  payload: unknown,
  store: PreferencesStore,
  userId: string
): CloseSignalIngestResult {
  const validate = getValidator(repoRoot);
  const ok = validate(payload);
  if (!ok) {
    const messages = (validate.errors || []).map((e) => `${e.instancePath || '<root>'}: ${e.message}`);
    throw new CloseSignalValidationError('CloseSignal failed schema validation', messages);
  }

  const closeSignal = payload as {
    id: string;
    path_id: string;
    status: string;
    decisions_made?: Array<{ key: string; value?: unknown; source?: string }>;
    context_residue?: {
      confirmed?: Record<string, unknown>;
      learned_preferences?: Record<string, unknown>;
    };
  };

  const learned = closeSignal.context_residue?.learned_preferences || {};
  const preferencesWritten = store.ingestLearnedPreferences(userId, learned, 'inferred', 0.85);

  // Also ingest confirmed decisions as explicit preferences (higher confidence)
  const confirmed = closeSignal.context_residue?.confirmed || {};
  for (const [key, value] of Object.entries(confirmed)) {
    store.upsert(userId, { key, value, confidence: 0.95, source: 'explicit' });
  }
  const totalWritten = preferencesWritten + Object.keys(confirmed).length;

  return {
    accepted: true,
    close_signal_id: closeSignal.id,
    path_id: closeSignal.path_id,
    status: closeSignal.status,
    preferences_written: totalWritten,
    decisions_count: (closeSignal.decisions_made || []).length,
  };
}
