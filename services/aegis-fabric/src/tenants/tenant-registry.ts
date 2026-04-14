/**
 * Aegis Enterprise Fabric — Tenant Registry
 *
 * CRUD operations for tenants. In-memory Map backed by .aegis-data/tenants.json.
 * API key generation via crypto.randomBytes.
 */

import * as crypto from 'crypto';
import {
  UUID, Timestamp, SHA256, TenantData, TenantTier, TenantQuotas,
  IsolationModel, Mode, DEFAULT_QUOTAS,
} from '../core/types.js';
import { generateUUID, now, hashState } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export interface TenantRecord {
  id: UUID;
  data: TenantData;
}

interface TenantsFile {
  tenants: TenantRecord[];
  updated_at: Timestamp;
}

export class TenantRegistry {
  private tenants: Map<UUID, TenantRecord> = new Map();
  private keyToTenant: Map<SHA256, UUID> = new Map();  // api_key_hash → tenant_id
  private storage: AegisStorage;

  constructor(storage: AegisStorage) {
    this.storage = storage;
    this.load();
  }

  async createTenant(opts: {
    name: string;
    tier?: TenantTier;
    mode?: Mode;
    isolation_model?: IsolationModel;
    quotas?: Partial<TenantQuotas>;
  }): Promise<{ tenant: TenantRecord; apiKey: string }> {
    const id = generateUUID();
    const tier = opts.tier || 'FREE';
    const apiKey = crypto.randomBytes(32).toString('hex');
    const apiKeyHash = await hashState(apiKey);

    const data: TenantData = {
      name: opts.name,
      tier,
      mode: opts.mode || 'BUILD',
      isolation_model: opts.isolation_model || 'POOLED',
      quotas: { ...DEFAULT_QUOTAS[tier], ...opts.quotas },
      api_key_hash: apiKeyHash,
      capabilities: [],
      enabled: true,
      created_at: now(),
      updated_at: now(),
    };

    const record: TenantRecord = { id, data };
    this.tenants.set(id, record);
    this.keyToTenant.set(apiKeyHash, id);
    this.save();

    return { tenant: record, apiKey };
  }

  getTenant(tenantId: UUID): TenantRecord | null {
    return this.tenants.get(tenantId) || null;
  }

  async getTenantByApiKey(apiKey: string): Promise<TenantRecord | null> {
    const hash = await hashState(apiKey);
    const tenantId = this.keyToTenant.get(hash);
    if (!tenantId) return null;
    return this.tenants.get(tenantId) || null;
  }

  listTenants(): TenantRecord[] {
    return Array.from(this.tenants.values());
  }

  updateTenant(tenantId: UUID, updates: Partial<TenantData>): TenantRecord | null {
    const existing = this.tenants.get(tenantId);
    if (!existing) return null;

    existing.data = { ...existing.data, ...updates, updated_at: now() };
    this.tenants.set(tenantId, existing);
    this.save();
    return existing;
  }

  getTenantCount(): number {
    return this.tenants.size;
  }

  private load(): void {
    const file = this.storage.readGlobalFile<TenantsFile>('tenants.json');
    if (!file) return;

    for (const record of file.tenants) {
      this.tenants.set(record.id, record);
      this.keyToTenant.set(record.data.api_key_hash, record.id);
    }
  }

  private save(): void {
    const file: TenantsFile = {
      tenants: Array.from(this.tenants.values()),
      updated_at: now(),
    };
    this.storage.writeGlobalFile('tenants.json', file);
  }
}
