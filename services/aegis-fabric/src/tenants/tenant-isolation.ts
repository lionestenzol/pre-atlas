/**
 * Aegis Enterprise Fabric — Tenant Isolation
 *
 * Enforces tenant boundaries: API key validation, quota checks, access control.
 */

import { UUID, TenantData, TenantQuotas } from '../core/types.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export interface QuotaCheckResult {
  allowed: boolean;
  reason?: string;
  remaining?: number;
}

export function checkEntityQuota(
  storage: AegisStorage,
  tenantId: UUID,
  quotas: TenantQuotas
): QuotaCheckResult {
  const stats = storage.getStats(tenantId);
  if (stats.entities >= quotas.max_entities) {
    return {
      allowed: false,
      reason: `Entity limit reached (${stats.entities}/${quotas.max_entities})`,
    };
  }
  return { allowed: true, remaining: quotas.max_entities - stats.entities };
}

export function checkDeltaQuota(
  storage: AegisStorage,
  tenantId: UUID,
  quotas: TenantQuotas
): QuotaCheckResult {
  const count = storage.getDeltaCount(tenantId);
  if (count >= quotas.max_delta_log_size) {
    return {
      allowed: false,
      reason: `Delta log limit reached (${count}/${quotas.max_delta_log_size})`,
    };
  }
  return { allowed: true, remaining: quotas.max_delta_log_size - count };
}

export function validateTenantEnabled(tenant: TenantData): { valid: boolean; reason?: string } {
  if (!tenant.enabled) {
    return { valid: false, reason: 'Tenant is disabled' };
  }
  return { valid: true };
}
