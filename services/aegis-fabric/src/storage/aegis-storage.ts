/**
 * Aegis Enterprise Fabric — Multi-Tenant Storage
 *
 * Per-tenant file-based storage with entities and deltas.
 * Directory structure: .aegis-data/tenants/{tenant_id}/entities.json + deltas.json
 */

import * as fs from 'fs';
import * as path from 'path';
import { Entity, Delta, AegisEntityType, UUID } from '../core/types.js';

export interface AegisStorageConfig {
  dataDir: string;
}

export class AegisStorage {
  private dataDir: string;

  constructor(config: AegisStorageConfig) {
    this.dataDir = config.dataDir;
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }
  }

  // === TENANT DATA DIRECTORY ===

  private tenantDir(tenantId: UUID): string {
    const dir = path.join(this.dataDir, 'tenants', tenantId);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    return dir;
  }

  private entitiesFile(tenantId: UUID): string {
    return path.join(this.tenantDir(tenantId), 'entities.json');
  }

  private deltasFile(tenantId: UUID): string {
    return path.join(this.tenantDir(tenantId), 'deltas.json');
  }

  // === GLOBAL FILES ===

  getGlobalFilePath(filename: string): string {
    return path.join(this.dataDir, filename);
  }

  readGlobalFile<T>(filename: string): T | null {
    const filePath = this.getGlobalFilePath(filename);
    if (!fs.existsSync(filePath)) return null;
    try {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T;
    } catch {
      return null;
    }
  }

  writeGlobalFile(filename: string, data: unknown): void {
    const filePath = this.getGlobalFilePath(filename);
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  }

  // === ENTITY OPERATIONS (per tenant) ===

  saveEntity(tenantId: UUID, entity: Entity, state: unknown): void {
    const entities = this.loadEntities(tenantId);
    entities.set(entity.entity_id, { entity, state });
    this.writeEntities(tenantId, entities);
  }

  loadEntity<T>(tenantId: UUID, entityId: UUID): { entity: Entity; state: T } | null {
    const entities = this.loadEntities(tenantId);
    const result = entities.get(entityId);
    if (!result) return null;
    return result as { entity: Entity; state: T };
  }

  loadEntitiesByType<T>(tenantId: UUID, type: AegisEntityType): Array<{ entity: Entity; state: T }> {
    const entities = this.loadEntities(tenantId);
    const results: Array<{ entity: Entity; state: T }> = [];
    for (const [, data] of entities) {
      if (data.entity.entity_type === type) {
        results.push(data as { entity: Entity; state: T });
      }
    }
    return results;
  }

  loadAllEntities(tenantId: UUID): Map<string, { entity: Entity; state: unknown }> {
    return this.loadEntities(tenantId);
  }

  deleteEntity(tenantId: UUID, entityId: UUID): boolean {
    const entities = this.loadEntities(tenantId);
    const deleted = entities.delete(entityId);
    if (deleted) {
      this.writeEntities(tenantId, entities);
    }
    return deleted;
  }

  private loadEntities(tenantId: UUID): Map<string, { entity: Entity; state: unknown }> {
    const file = this.entitiesFile(tenantId);
    if (!fs.existsSync(file)) return new Map();
    try {
      const raw = fs.readFileSync(file, 'utf-8');
      const arr = JSON.parse(raw) as Array<[string, { entity: Entity; state: unknown }]>;
      return new Map(arr);
    } catch {
      return new Map();
    }
  }

  private writeEntities(tenantId: UUID, entities: Map<string, { entity: Entity; state: unknown }>): void {
    const arr = Array.from(entities.entries());
    fs.writeFileSync(this.entitiesFile(tenantId), JSON.stringify(arr, null, 2));
  }

  // === DELTA OPERATIONS (per tenant) ===

  appendDelta(tenantId: UUID, delta: Delta): void {
    const deltas = this.loadDeltas(tenantId);
    deltas.push(delta);
    this.writeDeltas(tenantId, deltas);
  }

  loadDeltas(tenantId: UUID): Delta[] {
    const file = this.deltasFile(tenantId);
    if (!fs.existsSync(file)) return [];
    try {
      return JSON.parse(fs.readFileSync(file, 'utf-8')) as Delta[];
    } catch {
      return [];
    }
  }

  loadDeltasForEntity(tenantId: UUID, entityId: UUID): Delta[] {
    return this.loadDeltas(tenantId).filter(d => d.entity_id === entityId);
  }

  getDeltaCount(tenantId: UUID): number {
    return this.loadDeltas(tenantId).length;
  }

  private writeDeltas(tenantId: UUID, deltas: Delta[]): void {
    fs.writeFileSync(this.deltasFile(tenantId), JSON.stringify(deltas, null, 2));
  }

  // === JSONL APPEND (for audit logs, request logs) ===

  appendJsonl(filePath: string, entry: unknown): void {
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.appendFileSync(filePath, JSON.stringify(entry) + '\n');
  }

  readJsonl<T>(filePath: string): T[] {
    if (!fs.existsSync(filePath)) return [];
    try {
      const lines = fs.readFileSync(filePath, 'utf-8').trim().split('\n').filter(Boolean);
      return lines.map(line => JSON.parse(line) as T);
    } catch {
      return [];
    }
  }

  // === STATS ===

  getStats(tenantId: UUID): { entities: number; deltas: number; bytes: number } {
    const entities = this.loadEntities(tenantId);
    const deltas = this.loadDeltas(tenantId);

    let bytes = 0;
    const ef = this.entitiesFile(tenantId);
    const df = this.deltasFile(tenantId);
    if (fs.existsSync(ef)) bytes += fs.statSync(ef).size;
    if (fs.existsSync(df)) bytes += fs.statSync(df).size;

    return { entities: entities.size, deltas: deltas.length, bytes };
  }

  // === DATA DIR ACCESS ===

  getDataDir(): string {
    return this.dataDir;
  }

  getTenantDir(tenantId: UUID): string {
    return this.tenantDir(tenantId);
  }
}
