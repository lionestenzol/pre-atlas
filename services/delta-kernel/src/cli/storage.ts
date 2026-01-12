/**
 * Delta-State Fabric — Storage Layer
 *
 * Persists entities and deltas to JSON files.
 * Simple file-based storage for CLI usage.
 */

import * as fs from 'fs';
import * as path from 'path';
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
  private entitiesFile: string;
  private deltasFile: string;
  private dictionaryFile: string;

  constructor(config: StorageConfig) {
    this.dataDir = config.dataDir;
    this.entitiesFile = path.join(this.dataDir, 'entities.json');
    this.deltasFile = path.join(this.dataDir, 'deltas.json');
    this.dictionaryFile = path.join(this.dataDir, 'dictionary.json');

    // Ensure data directory exists
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }
  }

  // === ENTITY OPERATIONS ===

  saveEntity(entity: Entity, state: unknown): void {
    const entities = this.loadEntities();
    entities.set(entity.entity_id, { entity, state });
    this.writeEntities(entities);
  }

  loadEntity<T>(entityId: string): { entity: Entity; state: T } | null {
    const entities = this.loadEntities();
    const result = entities.get(entityId);
    if (!result) return null;
    return result as { entity: Entity; state: T };
  }

  loadEntitiesByType<T>(type: EntityType): Array<{ entity: Entity; state: T }> {
    const entities = this.loadEntities();
    const results: Array<{ entity: Entity; state: T }> = [];

    for (const [_, data] of entities) {
      if (data.entity.entity_type === type) {
        results.push(data as { entity: Entity; state: T });
      }
    }

    return results;
  }

  loadAllEntities(): Map<string, { entity: Entity; state: unknown }> {
    return this.loadEntities();
  }

  private loadEntities(): Map<string, { entity: Entity; state: unknown }> {
    if (!fs.existsSync(this.entitiesFile)) {
      return new Map();
    }

    try {
      const raw = fs.readFileSync(this.entitiesFile, 'utf-8');
      const arr = JSON.parse(raw) as Array<[string, { entity: Entity; state: unknown }]>;
      return new Map(arr);
    } catch {
      return new Map();
    }
  }

  private writeEntities(entities: Map<string, { entity: Entity; state: unknown }>): void {
    const arr = Array.from(entities.entries());
    fs.writeFileSync(this.entitiesFile, JSON.stringify(arr, null, 2));
  }

  // === DELTA OPERATIONS ===

  appendDelta(delta: Delta): void {
    const deltas = this.loadDeltas();
    deltas.push(delta);
    this.writeDeltas(deltas);
  }

  appendDeltas(newDeltas: Delta[]): void {
    const deltas = this.loadDeltas();
    deltas.push(...newDeltas);
    this.writeDeltas(deltas);
  }

  loadDeltas(): Delta[] {
    if (!fs.existsSync(this.deltasFile)) {
      return [];
    }

    try {
      const raw = fs.readFileSync(this.deltasFile, 'utf-8');
      return JSON.parse(raw) as Delta[];
    } catch {
      return [];
    }
  }

  loadDeltasForEntity(entityId: string): Delta[] {
    const deltas = this.loadDeltas();
    return deltas.filter(d => d.entity_id === entityId);
  }

  private writeDeltas(deltas: Delta[]): void {
    fs.writeFileSync(this.deltasFile, JSON.stringify(deltas, null, 2));
  }

  // === DICTIONARY OPERATIONS ===

  saveDictionary(dict: DictionaryState): void {
    const serialized = {
      tokens: Array.from(dict.tokens.values()).map(t => ({
        tokenId: t.state.token_id,
        value: t.state.value,
        frequency: t.state.frequency,
      })),
      patterns: Array.from(dict.patterns.values()).map(p => ({
        patternId: p.state.pattern_id,
        tokenSequence: p.state.token_sequence,
        frequency: p.state.frequency,
      })),
      motifs: Array.from(dict.motifs.values()).map(m => ({
        motifId: m.state.motif_id,
        patternSequence: m.state.pattern_sequence,
        slots: m.state.slots,
        frequency: m.state.frequency,
      })),
    };

    fs.writeFileSync(this.dictionaryFile, JSON.stringify(serialized, null, 2));
  }

  loadDictionaryData(): StoredData['dictionary'] | null {
    if (!fs.existsSync(this.dictionaryFile)) {
      return null;
    }

    try {
      const raw = fs.readFileSync(this.dictionaryFile, 'utf-8');
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  // === UTILITY ===

  clear(): void {
    if (fs.existsSync(this.entitiesFile)) fs.unlinkSync(this.entitiesFile);
    if (fs.existsSync(this.deltasFile)) fs.unlinkSync(this.deltasFile);
    if (fs.existsSync(this.dictionaryFile)) fs.unlinkSync(this.dictionaryFile);
  }

  getStats(): { entities: number; deltas: number; bytes: number } {
    const entities = this.loadEntities();
    const deltas = this.loadDeltas();

    let bytes = 0;
    if (fs.existsSync(this.entitiesFile)) {
      bytes += fs.statSync(this.entitiesFile).size;
    }
    if (fs.existsSync(this.deltasFile)) {
      bytes += fs.statSync(this.deltasFile).size;
    }
    if (fs.existsSync(this.dictionaryFile)) {
      bytes += fs.statSync(this.dictionaryFile).size;
    }

    return {
      entities: entities.size,
      deltas: deltas.length,
      bytes,
    };
  }
}
