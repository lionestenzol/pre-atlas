/**
 * Aegis Enterprise Fabric — Approval Queue
 *
 * Human-in-the-loop approval workflow for high-risk actions.
 * Submit → PENDING → APPROVED/REJECTED/EXPIRED
 */

import {
  UUID, ApprovalData, ApprovalWorkflowStatus, AgentActionName,
  CanonicalAgentAction, Entity,
} from '../core/types.js';
import { createEntity, generateUUID, now } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';

const DEFAULT_EXPIRY_MS = 3_600_000;  // 1 hour

export class ApprovalQueue {
  private storage: AegisStorage;

  constructor(storage: AegisStorage) {
    this.storage = storage;
  }

  async submit(action: CanonicalAgentAction, expiryMs?: number): Promise<{ approvalId: UUID; entity: Entity }> {
    const approvalData: ApprovalData = {
      tenant_id: action.tenant_id,
      action_id: action.action_id,
      agent_id: action.agent_id,
      action: action.action,
      params: action.params,
      status: 'PENDING',
      requested_at: now(),
      decided_at: null,
      decided_by: null,
      reason: null,
      expires_at: now() + (expiryMs || DEFAULT_EXPIRY_MS),
    };

    const { entity, delta } = await createEntity('aegis_approval', approvalData, action.tenant_id);
    this.storage.saveEntity(action.tenant_id, entity, approvalData);
    this.storage.appendDelta(action.tenant_id, delta);

    // Console notification for prototype
    console.log(`[APPROVAL REQUIRED] Tenant=${action.tenant_id} Action=${action.action} ApprovalID=${entity.entity_id}`);

    return { approvalId: entity.entity_id, entity };
  }

  listPending(tenantId: UUID): Array<{ entity: Entity; data: ApprovalData }> {
    const all = this.storage.loadEntitiesByType<ApprovalData>(tenantId, 'aegis_approval');
    return all
      .filter(a => a.state.status === 'PENDING')
      .map(a => ({ entity: a.entity, data: a.state }));
  }

  getApproval(tenantId: UUID, approvalId: UUID): { entity: Entity; data: ApprovalData } | null {
    const result = this.storage.loadEntity<ApprovalData>(tenantId, approvalId);
    if (!result || result.entity.entity_type !== 'aegis_approval') return null;
    return { entity: result.entity, data: result.state };
  }

  decide(tenantId: UUID, approvalId: UUID, status: 'APPROVED' | 'REJECTED', decidedBy: string, reason?: string): ApprovalData | null {
    const approval = this.getApproval(tenantId, approvalId);
    if (!approval) return null;
    if (approval.data.status !== 'PENDING') return null;

    approval.data.status = status;
    approval.data.decided_at = now();
    approval.data.decided_by = decidedBy;
    approval.data.reason = reason || null;

    this.storage.saveEntity(tenantId, approval.entity, approval.data);

    console.log(`[APPROVAL ${status}] ID=${approvalId} By=${decidedBy}`);

    return approval.data;
  }

  checkExpirations(tenantId: UUID): number {
    const pending = this.listPending(tenantId);
    let expired = 0;

    for (const { entity, data } of pending) {
      if (now() > data.expires_at) {
        data.status = 'EXPIRED';
        data.decided_at = now();
        data.decided_by = 'system';
        data.reason = 'Approval expired';
        this.storage.saveEntity(tenantId, entity, data);
        expired++;
      }
    }

    return expired;
  }
}
