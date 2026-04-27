/**
 * Signals store - SQLite-backed Signal.v1 storage.
 *
 * Phase 3c of doctrine/04_BUILD_PLAN.md, persistent variant
 * (Ship Target #1 of optogon-stack-three-gaps-handoff.md).
 *
 * Persists every Signal.v1 emitted by any layer so InPACT can poll
 * the active set and resolved approvals stay history-able.
 *
 * Validates every ingested signal against contracts/schemas/Signal.v1.json
 * before accepting. Resolution marks rows resolved (does not delete).
 */

import { existsSync, mkdirSync, readFileSync } from 'fs';
import { join } from 'path';
import Database from 'better-sqlite3';
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

const DDL = `
  CREATE TABLE IF NOT EXISTS signals (
    id              TEXT PRIMARY KEY,
    emitted_at      TEXT NOT NULL,
    source_layer    TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    priority        TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    resolved_at     TEXT,
    resolved_action TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_signals_emitted ON signals(emitted_at);
  CREATE INDEX IF NOT EXISTS idx_signals_unresolved ON signals(resolved_at);

  CREATE TABLE IF NOT EXISTS signal_resolutions (
    signal_id     TEXT PRIMARY KEY,
    action_id     TEXT NOT NULL,
    resolved_at   TEXT NOT NULL
  );
`;

export class SignalValidationError extends Error {
  readonly details: string[];
  constructor(message: string, details: string[]) {
    super(`${message}: ${details.join('; ')}`);
    this.name = 'SignalValidationError';
    this.details = details;
  }
}

export class SignalsStore {
  private db: Database.Database;
  private validator: ValidateFunction;

  constructor(dataDir: string, repoRoot: string) {
    if (!existsSync(dataDir)) mkdirSync(dataDir, { recursive: true });
    const dbPath = join(dataDir, 'signals.db');
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('busy_timeout = 5000');
    this.db.exec(DDL);

    const schemaPath = join(repoRoot, 'contracts', 'schemas', 'Signal.v1.json');
    const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
    const ajv = new Ajv({ strict: false, allErrors: true });
    addFormats(ajv);
    this.validator = ajv.compile(schema);
  }

  ingest(payload: unknown): Signal {
    const ok = this.validator(payload);
    if (!ok) {
      const messages = (this.validator.errors || []).map(
        (e) => `${e.instancePath || '<root>'}: ${e.message}`
      );
      throw new SignalValidationError('Signal failed schema validation', messages);
    }
    const signal = payload as Signal;
    this.db
      .prepare(
        `INSERT OR REPLACE INTO signals
           (id, emitted_at, source_layer, signal_type, priority, payload_json, resolved_at, resolved_action)
         VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)`
      )
      .run(
        signal.id,
        signal.emitted_at,
        signal.source_layer,
        signal.signal_type,
        signal.priority,
        JSON.stringify(signal.payload)
      );
    return signal;
  }

  /** List active (unresolved) signals, newest first. Optional ?since=timestamp filter. */
  list(since?: string): Signal[] {
    const rows = since
      ? (this.db
          .prepare(
            `SELECT id, emitted_at, source_layer, signal_type, priority, payload_json
               FROM signals
              WHERE resolved_at IS NULL AND emitted_at > ?
              ORDER BY emitted_at DESC`
          )
          .all(since) as SignalRow[])
      : (this.db
          .prepare(
            `SELECT id, emitted_at, source_layer, signal_type, priority, payload_json
               FROM signals
              WHERE resolved_at IS NULL
              ORDER BY emitted_at DESC`
          )
          .all() as SignalRow[]);
    return rows.map(rowToSignal);
  }

  /** Mark a signal resolved. Returns null if not found or already resolved. */
  resolve(signalId: string, actionId: string): SignalResolution | null {
    const row = this.db
      .prepare(`SELECT id, resolved_at FROM signals WHERE id = ?`)
      .get(signalId) as { id: string; resolved_at: string | null } | undefined;
    if (!row) return null;
    if (row.resolved_at) return null;
    const resolvedAt = new Date().toISOString();
    this.db
      .prepare(`UPDATE signals SET resolved_at = ?, resolved_action = ? WHERE id = ?`)
      .run(resolvedAt, actionId, signalId);
    this.db
      .prepare(
        `INSERT OR REPLACE INTO signal_resolutions (signal_id, action_id, resolved_at) VALUES (?, ?, ?)`
      )
      .run(signalId, actionId, resolvedAt);
    return { signal_id: signalId, action_id: actionId, resolved_at: resolvedAt };
  }

  listResolutions(): SignalResolution[] {
    const rows = this.db
      .prepare(`SELECT signal_id, action_id, resolved_at FROM signal_resolutions ORDER BY resolved_at DESC`)
      .all() as Array<{ signal_id: string; action_id: string; resolved_at: string }>;
    return rows.map((r) => ({ signal_id: r.signal_id, action_id: r.action_id, resolved_at: r.resolved_at }));
  }

  clearAll(): void {
    this.db.exec('DELETE FROM signal_resolutions; DELETE FROM signals;');
  }

  close(): void {
    this.db.close();
  }
}

interface SignalRow {
  id: string;
  emitted_at: string;
  source_layer: string;
  signal_type: string;
  priority: string;
  payload_json: string;
}

function rowToSignal(r: SignalRow): Signal {
  return {
    schema_version: '1.0',
    id: r.id,
    emitted_at: r.emitted_at,
    source_layer: r.source_layer as Signal['source_layer'],
    signal_type: r.signal_type as Signal['signal_type'],
    priority: r.priority as Signal['priority'],
    payload: JSON.parse(r.payload_json),
  };
}

// ---- Module-level convenience wrappers (back-compat with the previous
//      ring-buffer API used by server.ts). One process-wide store, lazily
//      constructed when ingest/list/resolve is first called.

let _store: SignalsStore | null = null;
let _storeRepoRoot: string | null = null;

function getStore(repoRoot: string): SignalsStore {
  if (_store && _storeRepoRoot === repoRoot) return _store;
  if (_store) {
    _store.close();
    _store = null;
  }
  const dataDir = process.env.DELTA_DATA_DIR || join(require('os').homedir(), '.delta-fabric');
  _store = new SignalsStore(dataDir, repoRoot);
  _storeRepoRoot = repoRoot;
  return _store;
}

/** Ingest a signal. Throws SignalValidationError on schema failure. */
export function ingestSignal(repoRoot: string, payload: unknown): Signal {
  return getStore(repoRoot).ingest(payload);
}

/** List active signals, newest first. Optional ?since=timestamp filter. */
export function listSignals(since?: string, repoRoot?: string): Signal[] {
  if (!_store && !repoRoot) {
    // No store configured yet and no repoRoot to construct one. Return empty.
    return [];
  }
  return getStore(_storeRepoRoot || repoRoot!).list(since);
}

/** Record resolution of an approval_required signal. Returns null if not found. */
export function resolveSignal(signalId: string, actionId: string): SignalResolution | null {
  if (!_store) return null;
  return _store.resolve(signalId, actionId);
}

export function listResolutions(): SignalResolution[] {
  if (!_store) return [];
  return _store.listResolutions();
}

export function clearAll(): void {
  if (_store) _store.clearAll();
}

/** Test-only: reset the module-level store. */
export function _resetStoreForTests(): void {
  if (_store) {
    _store.close();
    _store = null;
    _storeRepoRoot = null;
  }
}
