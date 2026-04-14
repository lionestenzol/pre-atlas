/**
 * Delta-State Fabric — SQLite Storage Layer
 *
 * Drop-in replacement for file-based Storage.
 * Uses better-sqlite3 with WAL mode for:
 *   - Atomic writes (no hash chain forks from concurrent daemon jobs)
 *   - O(1) delta appends (vs O(n) read-all + rewrite)
 *   - Concurrent read support during writes
 */

import * as fs from 'fs';
import * as path from 'path';
import Database from 'better-sqlite3';
import { Entity, Delta, EntityType } from '../core/types';
import { DictionaryState } from '../core/dictionary';

export interface StorageConfig {
  dataDir: string;
}

export interface StoredData {
  entities: Map<string, { entity: Entity; state: unknown }>;
  deltas: Delta[];
  dictionary: {
    tokens: Array<{ tokenId: string; value: string; frequency: number }>;
    patterns: Array<{ patternId: string; tokenSequence: string[]; frequency: number }>;
    motifs: Array<{ motifId: string; patternSequence: string[]; slots: string[]; frequency: number }>;
  };
}

export class Storage {
  private dataDir: string;
  private db: Database.Database;

  constructor(config: StorageConfig) {
    this.dataDir = config.dataDir;

    // Ensure data directory exists
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }

    const dbPath = path.join(this.dataDir, 'state.db');
    this.db = new Database(dbPath);

    // WAL mode for concurrent reads during writes + busy timeout
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('busy_timeout = 5000');

    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        current_version INTEGER NOT NULL,
        current_hash TEXT NOT NULL,
        is_archived INTEGER NOT NULL DEFAULT 0,
        state TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);

      CREATE TABLE IF NOT EXISTS deltas (
        delta_id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        author TEXT NOT NULL,
        patch TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        new_hash TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_deltas_entity ON deltas(entity_id);
      CREATE INDEX IF NOT EXISTS idx_deltas_timestamp ON deltas(timestamp);

      CREATE TABLE IF NOT EXISTS dictionary_tokens (
        token_id TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        frequency INTEGER NOT NULL DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS dictionary_patterns (
        pattern_id TEXT PRIMARY KEY,
        token_sequence TEXT NOT NULL,
        frequency INTEGER NOT NULL DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS dictionary_motifs (
        motif_id TEXT PRIMARY KEY,
        pattern_sequence TEXT NOT NULL,
        slots TEXT NOT NULL,
        frequency INTEGER NOT NULL DEFAULT 0
      );
    `);
  }

  // === ENTITY OPERATIONS ===

  saveEntity(entity: Entity, state: unknown): void {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO entities (entity_id, entity_type, created_at, current_version, current_hash, is_archived, state)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      entity.entity_id,
      entity.entity_type,
      entity.created_at,
      entity.current_version,
      entity.current_hash,
      entity.is_archived ? 1 : 0,
      JSON.stringify(state),
    );
  }

  loadEntity<T>(entityId: string): { entity: Entity; state: T } | null {
    const row = this.db.prepare('SELECT * FROM entities WHERE entity_id = ?').get(entityId) as EntityRow | undefined;
    if (!row) return null;
    return rowToEntityState<T>(row);
  }

  loadEntitiesByType<T>(type: EntityType): Array<{ entity: Entity; state: T }> {
    const rows = this.db.prepare('SELECT * FROM entities WHERE entity_type = ?').all(type) as EntityRow[];
    return rows.map(row => rowToEntityState<T>(row));
  }

  loadAllEntities(): Map<string, { entity: Entity; state: unknown }> {
    const rows = this.db.prepare('SELECT * FROM entities').all() as EntityRow[];
    const map = new Map<string, { entity: Entity; state: unknown }>();
    for (const row of rows) {
      const { entity, state } = rowToEntityState(row);
      map.set(entity.entity_id, { entity, state });
    }
    return map;
  }

  // === DELTA OPERATIONS ===

  appendDelta(delta: Delta): void {
    const stmt = this.db.prepare(`
      INSERT INTO deltas (delta_id, entity_id, timestamp, author, patch, prev_hash, new_hash)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      delta.delta_id,
      delta.entity_id,
      delta.timestamp,
      delta.author,
      JSON.stringify(delta.patch),
      delta.prev_hash,
      delta.new_hash,
    );
  }

  appendDeltas(newDeltas: Delta[]): void {
    const stmt = this.db.prepare(`
      INSERT INTO deltas (delta_id, entity_id, timestamp, author, patch, prev_hash, new_hash)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    const insertMany = this.db.transaction((deltas: Delta[]) => {
      for (const delta of deltas) {
        stmt.run(
          delta.delta_id,
          delta.entity_id,
          delta.timestamp,
          delta.author,
          JSON.stringify(delta.patch),
          delta.prev_hash,
          delta.new_hash,
        );
      }
    });

    insertMany(newDeltas);
  }

  loadDeltas(): Delta[] {
    const rows = this.db.prepare('SELECT * FROM deltas ORDER BY timestamp ASC').all() as DeltaRow[];
    return rows.map(rowToDelta);
  }

  loadDeltasForEntity(entityId: string): Delta[] {
    const rows = this.db.prepare('SELECT * FROM deltas WHERE entity_id = ? ORDER BY timestamp ASC').all(entityId) as DeltaRow[];
    return rows.map(rowToDelta);
  }

  // === DICTIONARY OPERATIONS ===

  saveDictionary(dict: DictionaryState): void {
    const saveDictTx = this.db.transaction(() => {
      // Clear existing
      this.db.exec('DELETE FROM dictionary_tokens');
      this.db.exec('DELETE FROM dictionary_patterns');
      this.db.exec('DELETE FROM dictionary_motifs');

      // Insert tokens
      const tokenStmt = this.db.prepare('INSERT INTO dictionary_tokens (token_id, value, frequency) VALUES (?, ?, ?)');
      for (const [, t] of dict.tokens) {
        tokenStmt.run(t.state.token_id, t.state.value, t.state.frequency);
      }

      // Insert patterns
      const patternStmt = this.db.prepare('INSERT INTO dictionary_patterns (pattern_id, token_sequence, frequency) VALUES (?, ?, ?)');
      for (const [, p] of dict.patterns) {
        patternStmt.run(p.state.pattern_id, JSON.stringify(p.state.token_sequence), p.state.frequency);
      }

      // Insert motifs
      const motifStmt = this.db.prepare('INSERT INTO dictionary_motifs (motif_id, pattern_sequence, slots, frequency) VALUES (?, ?, ?, ?)');
      for (const [, m] of dict.motifs) {
        motifStmt.run(m.state.motif_id, JSON.stringify(m.state.pattern_sequence), JSON.stringify(m.state.slots), m.state.frequency);
      }
    });

    saveDictTx();
  }

  loadDictionaryData(): StoredData['dictionary'] | null {
    const tokens = this.db.prepare('SELECT * FROM dictionary_tokens').all() as Array<{ token_id: string; value: string; frequency: number }>;
    const patterns = this.db.prepare('SELECT * FROM dictionary_patterns').all() as Array<{ pattern_id: string; token_sequence: string; frequency: number }>;
    const motifs = this.db.prepare('SELECT * FROM dictionary_motifs').all() as Array<{ motif_id: string; pattern_sequence: string; slots: string; frequency: number }>;

    if (tokens.length === 0 && patterns.length === 0 && motifs.length === 0) {
      return null;
    }

    return {
      tokens: tokens.map(t => ({ tokenId: t.token_id, value: t.value, frequency: t.frequency })),
      patterns: patterns.map(p => ({
        patternId: p.pattern_id,
        tokenSequence: JSON.parse(p.token_sequence),
        frequency: p.frequency,
      })),
      motifs: motifs.map(m => ({
        motifId: m.motif_id,
        patternSequence: JSON.parse(m.pattern_sequence),
        slots: JSON.parse(m.slots),
        frequency: m.frequency,
      })),
    };
  }

  // === UTILITY ===

  clear(): void {
    this.db.exec('DELETE FROM entities');
    this.db.exec('DELETE FROM deltas');
    this.db.exec('DELETE FROM dictionary_tokens');
    this.db.exec('DELETE FROM dictionary_patterns');
    this.db.exec('DELETE FROM dictionary_motifs');
  }

  getStats(): { entities: number; deltas: number; bytes: number } {
    const entitiesCount = (this.db.prepare('SELECT COUNT(*) as count FROM entities').get() as { count: number }).count;
    const deltasCount = (this.db.prepare('SELECT COUNT(*) as count FROM deltas').get() as { count: number }).count;

    // Get DB file size
    const dbPath = path.join(this.dataDir, 'state.db');
    let bytes = 0;
    if (fs.existsSync(dbPath)) {
      bytes = fs.statSync(dbPath).size;
      // Include WAL file size if present
      const walPath = dbPath + '-wal';
      if (fs.existsSync(walPath)) {
        bytes += fs.statSync(walPath).size;
      }
    }

    return { entities: entitiesCount, deltas: deltasCount, bytes };
  }

  /** Close the database connection. Call during graceful shutdown. */
  close(): void {
    this.db.close();
  }
}

// === ROW TYPES & CONVERTERS ===

interface EntityRow {
  entity_id: string;
  entity_type: string;
  created_at: number;
  current_version: number;
  current_hash: string;
  is_archived: number;
  state: string;
}

interface DeltaRow {
  delta_id: string;
  entity_id: string;
  timestamp: number;
  author: string;
  patch: string;
  prev_hash: string;
  new_hash: string;
}

function rowToEntityState<T = unknown>(row: EntityRow): { entity: Entity; state: T } {
  return {
    entity: {
      entity_id: row.entity_id,
      entity_type: row.entity_type as EntityType,
      created_at: row.created_at,
      current_version: row.current_version,
      current_hash: row.current_hash,
      is_archived: row.is_archived === 1,
    },
    state: JSON.parse(row.state) as T,
  };
}

function rowToDelta(row: DeltaRow): Delta {
  return {
    delta_id: row.delta_id,
    entity_id: row.entity_id,
    timestamp: row.timestamp,
    author: row.author as Delta['author'],
    patch: JSON.parse(row.patch),
    prev_hash: row.prev_hash,
    new_hash: row.new_hash,
  };
}
