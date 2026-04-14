/**
 * Delta Kernel — Tenant Routes
 *
 * POST /v1/tenants   — create a new tenant (provisions database)
 * GET  /v1/tenants   — list all tenants
 * GET  /v1/tenants/:id — get tenant by ID
 * PUT  /v1/tenants/:id — update tenant settings
 */

import type { FastifyInstance } from 'fastify';
import { generateUUID, sha256 } from '@aegis/shared';
import type { TenantTier, Mode, TenantQuotas } from '@aegis/shared';
import { DEFAULT_QUOTAS, tenantCreateSchema } from '@aegis/shared';
import type { PoolManager } from '../db/pool-manager.js';
import { provisionTenantDatabase } from '../db/tenant-db.js';

interface TenantRow {
  tenant_id: string;
  name: string;
  tier: TenantTier;
  mode: Mode;
  quotas: TenantQuotas;
  api_key_hash: string;
  db_name: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export function tenantRoutes(app: FastifyInstance, poolManager: PoolManager): void {
  const adminPool = poolManager.getAdminPool();

  // POST /v1/tenants
  app.post('/v1/tenants', { schema: tenantCreateSchema }, async (req, reply) => {
    const body = req.body as {
      name: string;
      tier?: TenantTier;
      mode?: Mode;
      quotas?: Partial<TenantQuotas>;
    };

    const tenantId = generateUUID();
    const tier: TenantTier = body.tier || 'FREE';
    const mode: Mode = body.mode || 'BUILD';
    const quotas: TenantQuotas = { ...DEFAULT_QUOTAS[tier], ...(body.quotas || {}) };

    // Generate API key and hash it
    const apiKey = `aegis_${generateUUID().replace(/-/g, '')}`;
    const apiKeyHash = sha256(apiKey);

    // Database name: aegis_tnt_{short_id}
    const dbName = `aegis_tnt_${tenantId.replace(/-/g, '').slice(0, 12)}`;
    const now = new Date().toISOString();

    // Insert tenant record in admin DB
    await adminPool.query(
      `INSERT INTO tenants (tenant_id, name, tier, mode, quotas, api_key_hash, db_name, enabled, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, true, $8, $8)`,
      [tenantId, body.name, tier, mode, JSON.stringify(quotas), apiKeyHash, dbName, now]
    );

    // Provision the tenant database
    await provisionTenantDatabase(poolManager, dbName);

    return reply.status(201).send({
      tenant_id: tenantId,
      name: body.name,
      tier,
      mode,
      quotas,
      db_name: dbName,
      api_key: apiKey, // Only returned on creation
      enabled: true,
      created_at: now,
    });
  });

  // GET /v1/tenants
  app.get('/v1/tenants', async (_req, reply) => {
    const res = await adminPool.query(
      'SELECT tenant_id, name, tier, mode, quotas, db_name, enabled, created_at, updated_at FROM tenants ORDER BY created_at DESC'
    );

    return reply.send({
      tenants: res.rows.map(mapTenantRow),
      count: res.rows.length,
    });
  });

  // GET /v1/tenants/:id
  app.get('/v1/tenants/:id', async (req, reply) => {
    const { id } = req.params as { id: string };

    const res = await adminPool.query(
      'SELECT tenant_id, name, tier, mode, quotas, db_name, enabled, created_at, updated_at FROM tenants WHERE tenant_id = $1',
      [id]
    );

    if (res.rows.length === 0) {
      return reply.status(404).send({ error: 'Tenant not found' });
    }

    return reply.send(mapTenantRow(res.rows[0]));
  });

  // PUT /v1/tenants/:id
  app.put('/v1/tenants/:id', async (req, reply) => {
    const { id } = req.params as { id: string };
    const body = req.body as {
      name?: string;
      tier?: TenantTier;
      mode?: Mode;
      quotas?: Partial<TenantQuotas>;
      enabled?: boolean;
    };

    const existing = await adminPool.query(
      'SELECT * FROM tenants WHERE tenant_id = $1',
      [id]
    );

    if (existing.rows.length === 0) {
      return reply.status(404).send({ error: 'Tenant not found' });
    }

    const row = existing.rows[0];
    const updates: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (body.name !== undefined) { updates.push(`name = $${idx++}`); values.push(body.name); }
    if (body.tier !== undefined) { updates.push(`tier = $${idx++}`); values.push(body.tier); }
    if (body.mode !== undefined) { updates.push(`mode = $${idx++}`); values.push(body.mode); }
    if (body.quotas !== undefined) {
      const merged = { ...row.quotas, ...body.quotas };
      updates.push(`quotas = $${idx++}`);
      values.push(JSON.stringify(merged));
    }
    if (body.enabled !== undefined) { updates.push(`enabled = $${idx++}`); values.push(body.enabled); }

    if (updates.length === 0) {
      return reply.send(mapTenantRow(row));
    }

    updates.push(`updated_at = $${idx++}`);
    values.push(new Date().toISOString());
    values.push(id);

    await adminPool.query(
      `UPDATE tenants SET ${updates.join(', ')} WHERE tenant_id = $${idx}`,
      values
    );

    const updated = await adminPool.query(
      'SELECT tenant_id, name, tier, mode, quotas, db_name, enabled, created_at, updated_at FROM tenants WHERE tenant_id = $1',
      [id]
    );

    return reply.send(mapTenantRow(updated.rows[0]));
  });
}

function mapTenantRow(row: Record<string, unknown>): Omit<TenantRow, 'api_key_hash'> {
  return {
    tenant_id: row.tenant_id as string,
    name: row.name as string,
    tier: row.tier as TenantTier,
    mode: row.mode as Mode,
    quotas: row.quotas as TenantQuotas,
    db_name: row.db_name as string,
    enabled: row.enabled as boolean,
    created_at: row.created_at instanceof Date ? row.created_at.toISOString() : row.created_at as string,
    updated_at: row.updated_at instanceof Date ? row.updated_at.toISOString() : row.updated_at as string,
  };
}
