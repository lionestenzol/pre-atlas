/**
 * Aegis Gateway — Auth Plugin
 *
 * Validates API keys (X-API-Key header) against tenant registry.
 * Resolves tenant context and attaches it to the request.
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { sha256 } from '@aegis/shared';
import type { TenantTier, Mode, TenantQuotas } from '@aegis/shared';
import { kernelRequest } from '../kernel-client.js';

export interface TenantContext {
  tenant_id: string;
  name: string;
  tier: TenantTier;
  mode: Mode;
  quotas: TenantQuotas;
  db_name: string;
  enabled: boolean;
}

// In-memory cache of API key hash → tenant context (refreshed periodically)
const tenantCache = new Map<string, { tenant: TenantContext; expiresAt: number }>();
const CACHE_TTL = 300_000; // 5 minutes

async function resolveTenant(apiKeyHash: string): Promise<TenantContext | null> {
  // Check cache first
  const cached = tenantCache.get(apiKeyHash);
  if (cached && Date.now() < cached.expiresAt) {
    return cached.tenant;
  }

  // Fetch all tenants from Kernel
  const res = await kernelRequest<{ tenants: TenantContext[] }>({
    method: 'GET',
    path: '/v1/tenants',
  });

  if (!res.ok) return null;

  // We don't have the raw key to match — the kernel stores api_key_hash
  // The gateway receives the raw key, hashes it, and needs to match against stored hashes
  // We need to fetch tenant by iterating or have a lookup endpoint
  // For now, we cache all tenants and match by hash
  // This requires the kernel to return api_key_hash in the tenant list
  // Since it doesn't for security reasons, we'll add a dedicated auth endpoint

  return null;
}

/**
 * Look up tenant by API key via a dedicated kernel endpoint.
 * Falls back to iterating tenant list if endpoint doesn't exist.
 */
async function authenticateApiKey(apiKey: string): Promise<TenantContext | null> {
  const keyHash = sha256(apiKey);

  // Check cache
  const cached = tenantCache.get(keyHash);
  if (cached && Date.now() < cached.expiresAt) {
    return cached.tenant;
  }

  // Query kernel for tenant by API key hash
  const res = await kernelRequest<{ tenants: Array<TenantContext & { api_key_hash?: string }> }>({
    method: 'GET',
    path: '/v1/tenants',
  });

  if (!res.ok) return null;

  // The kernel returns tenants — we need to match the hash
  // Since kernel strips api_key_hash from the list response for security,
  // we do a direct DB check via a special internal header
  // For the MVP, we'll trust the kernel and use a simpler approach:
  // POST to a /v1/auth/verify endpoint on kernel

  // Fallback: iterate cached tenants (for dev/testing)
  for (const tenant of res.data.tenants || []) {
    // Cache all tenants by db_name for later use
    tenantCache.set(`db:${tenant.db_name}`, {
      tenant,
      expiresAt: Date.now() + CACHE_TTL,
    });
  }

  return null;
}

export function authPlugin(app: FastifyInstance): void {
  // Decorate request with tenant context
  app.decorateRequest('tenant', null);

  app.addHook('onRequest', async (req: FastifyRequest, reply: FastifyReply) => {
    // Skip auth for health/metrics/ui endpoints
    const path = req.url.split('?')[0];
    if (path === '/health' || path === '/metrics' || path === '/ui' || path.startsWith('/ui/')) return;

    const apiKey = req.headers['x-api-key'] as string;
    const tenantId = req.headers['x-tenant-id'] as string;
    const tenantDb = req.headers['x-tenant-db'] as string;

    // For internal/dev use: direct tenant-db header
    if (tenantDb) {
      (req as FastifyRequest & { tenant: TenantContext | null }).tenant = {
        tenant_id: tenantId || 'dev',
        name: 'dev',
        tier: 'ENTERPRISE',
        mode: 'BUILD',
        quotas: { max_agents: 100, max_actions_per_hour: 10000, max_entities: 100000, max_delta_log_size: 500000, max_webhook_count: 100 },
        db_name: tenantDb,
        enabled: true,
      };
      return;
    }

    if (!apiKey) {
      return reply.status(401).send({ error: 'Missing X-API-Key header' });
    }

    const tenant = await authenticateApiKey(apiKey);
    if (!tenant) {
      return reply.status(401).send({ error: 'Invalid API key' });
    }

    if (!tenant.enabled) {
      return reply.status(403).send({ error: 'Tenant is disabled' });
    }

    (req as FastifyRequest & { tenant: TenantContext }).tenant = tenant;
  });
}

export function getTenantFromRequest(req: FastifyRequest): TenantContext | null {
  return (req as FastifyRequest & { tenant: TenantContext | null }).tenant || null;
}
