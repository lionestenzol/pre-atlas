/**
 * User preference store - SQLite-backed cross-session memory.
 * Per doctrine/02_ROSETTA_STONE.md Cross-Session User Memory.
 *
 * Phase 4 of doctrine/04_BUILD_PLAN.md. Owned by Atlas. Written by
 * Optogon (via close-signal learned_preferences). Read by Cortex
 * (when composing TaskPrompts) and Optogon (on session start).
 *
 * Upserts by (user_id, key): observed_count increments, confidence
 * is averaged across observations, last_observed is updated.
 */

import { existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import Database from 'better-sqlite3';

export interface PreferenceRecord {
  key: string;
  value: unknown;
  confidence: number;
  source: 'explicit' | 'inferred';
  observed_count: number;
  last_observed: string;
}

export interface BehavioralPattern {
  pattern: string;
  frequency: 'always' | 'usually' | 'sometimes';
  context?: string;
  first_observed?: string;
}

export interface UserPreferenceStoreRow {
  schema_version: '1.0';
  user_id: string;
  last_updated: string;
  preferences: PreferenceRecord[];
  behavioral_patterns?: BehavioralPattern[];
}

const DDL = `
  CREATE TABLE IF NOT EXISTS user_preferences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    key             TEXT NOT NULL,
    value_json      TEXT NOT NULL,
    confidence      REAL NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('explicit', 'inferred')),
    observed_count  INTEGER NOT NULL DEFAULT 1,
    last_observed   TEXT NOT NULL,
    UNIQUE(user_id, key)
  );
  CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
`;

export class PreferencesStore {
  private db: Database.Database;

  constructor(dataDir: string) {
    if (!existsSync(dataDir)) mkdirSync(dataDir, { recursive: true });
    const dbPath = join(dataDir, 'preferences.db');
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('busy_timeout = 5000');
    this.db.exec(DDL);
  }

  /** Upsert a preference. If exists, bump observed_count and running-average confidence. */
  upsert(userId: string, pref: Omit<PreferenceRecord, 'observed_count' | 'last_observed'>): void {
    const now = new Date().toISOString();
    const existing = this.db
      .prepare('SELECT observed_count, confidence FROM user_preferences WHERE user_id = ? AND key = ?')
      .get(userId, pref.key) as { observed_count: number; confidence: number } | undefined;

    if (existing) {
      const newCount = existing.observed_count + 1;
      // Running average confidence; tolerate a small EMA bias toward newer observations
      const newConfidence = (existing.confidence * existing.observed_count + pref.confidence) / newCount;
      this.db
        .prepare(
          `UPDATE user_preferences
              SET value_json = ?, confidence = ?, source = ?, observed_count = ?, last_observed = ?
            WHERE user_id = ? AND key = ?`
        )
        .run(
          JSON.stringify(pref.value ?? null),
          Math.min(Math.max(newConfidence, 0), 1),
          pref.source,
          newCount,
          now,
          userId,
          pref.key
        );
      return;
    }
    this.db
      .prepare(
        `INSERT INTO user_preferences (user_id, key, value_json, confidence, source, observed_count, last_observed)
         VALUES (?, ?, ?, ?, ?, 1, ?)`
      )
      .run(
        userId,
        pref.key,
        JSON.stringify(pref.value ?? null),
        Math.min(Math.max(pref.confidence, 0), 1),
        pref.source,
        now
      );
  }

  /** Upsert many learned_preferences entries from a CloseSignal.context_residue. */
  ingestLearnedPreferences(
    userId: string,
    learned: Record<string, unknown>,
    source: 'explicit' | 'inferred' = 'inferred',
    confidence = 0.85
  ): number {
    const insert = (key: string, value: unknown) => this.upsert(userId, { key, value, confidence, source });
    let count = 0;
    for (const [key, value] of Object.entries(learned || {})) {
      insert(key, value);
      count += 1;
    }
    return count;
  }

  /** Read the full preference store for a user, shaped as UserPreferenceStore.v1. */
  read(userId: string): UserPreferenceStoreRow {
    const rows = this.db
      .prepare(
        `SELECT key, value_json, confidence, source, observed_count, last_observed
           FROM user_preferences
          WHERE user_id = ?
          ORDER BY last_observed DESC`
      )
      .all(userId) as Array<{
        key: string;
        value_json: string;
        confidence: number;
        source: 'explicit' | 'inferred';
        observed_count: number;
        last_observed: string;
      }>;

    const preferences: PreferenceRecord[] = rows.map((r) => ({
      key: r.key,
      value: safeParse(r.value_json),
      confidence: r.confidence,
      source: r.source,
      observed_count: r.observed_count,
      last_observed: r.last_observed,
    }));

    const lastUpdated = preferences.length > 0 ? preferences[0].last_observed : new Date().toISOString();
    return {
      schema_version: '1.0',
      user_id: userId,
      last_updated: lastUpdated,
      preferences,
    };
  }

  clear(userId?: string): void {
    if (userId) {
      this.db.prepare('DELETE FROM user_preferences WHERE user_id = ?').run(userId);
    } else {
      this.db.prepare('DELETE FROM user_preferences').run();
    }
  }

  close(): void {
    this.db.close();
  }
}

function safeParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}
