/**
 * Aegis Enterprise Fabric — Health Check
 */

import { HealthResponse } from '../core/types.js';
import { AegisStorage } from '../storage/aegis-storage.js';
import { TenantRegistry } from '../tenants/tenant-registry.js';

const startTime = Date.now();
const VERSION = '0.1.0';

export function getHealth(storage: AegisStorage, tenantRegistry: TenantRegistry): HealthResponse {
  let storageAccessible = true;
  try {
    storage.readGlobalFile('tenants.json');
  } catch {
    storageAccessible = false;
  }

  return {
    status: storageAccessible ? 'healthy' : 'degraded',
    uptime_ms: Date.now() - startTime,
    version: VERSION,
    tenants_loaded: tenantRegistry.getTenantCount(),
    storage_accessible: storageAccessible,
  };
}
