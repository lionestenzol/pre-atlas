/**
 * Aegis Enterprise Fabric — Audit Log
 *
 * Append-only JSONL audit trail per tenant. Never modified, only appended.
 */

import * as path from 'path';
import {
  UUID, AuditEntry, AgentActionName, PolicyEffect,
} from '../core/types.js';
import { generateUUID } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export class AuditLog {
  private storage: AegisStorage;

  constructor(storage: AegisStorage) {
    this.storage = storage;
  }

  private auditFile(tenantId: UUID): string {
    return path.join(this.storage.getDataDir(), 'audit', tenantId, 'audit.jsonl');
  }

  append(entry: Omit<AuditEntry, 'audit_id'>): void {
    const fullEntry: AuditEntry = {
      audit_id: generateUUID(),
      ...entry,
    };
    this.storage.appendJsonl(this.auditFile(entry.tenant_id), fullEntry);
  }

  logAction(opts: {
    tenant_id: UUID;
    agent_id: UUID;
    action: AgentActionName;
    effect: PolicyEffect;
    entity_ids: UUID[];
    delta_id: UUID | null;
    metadata?: Record<string, unknown>;
  }): void {
    this.append({
      tenant_id: opts.tenant_id,
      agent_id: opts.agent_id,
      action: opts.action,
      effect: opts.effect,
      entity_ids_affected: opts.entity_ids,
      delta_id: opts.delta_id,
      timestamp: Date.now(),
      metadata: opts.metadata || {},
    });
  }

  getEntries(tenantId: UUID, limit?: number): AuditEntry[] {
    const entries = this.storage.readJsonl<AuditEntry>(this.auditFile(tenantId));
    return limit ? entries.slice(-limit) : entries;
  }

  getEntriesByAgent(tenantId: UUID, agentId: UUID): AuditEntry[] {
    return this.getEntries(tenantId).filter(e => e.agent_id === agentId);
  }

  getEntriesByAction(tenantId: UUID, action: AgentActionName): AuditEntry[] {
    return this.getEntries(tenantId).filter(e => e.action === action);
  }
}
