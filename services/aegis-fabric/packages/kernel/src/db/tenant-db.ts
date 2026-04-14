/**
 * Delta Kernel — Tenant Database Provisioning
 *
 * Creates a new PostgreSQL database per tenant and applies the tenant schema.
 * Uses the admin pool to execute CREATE DATABASE, then applies 002_tenant.sql.
 */

import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { PoolManager } from './pool-manager.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TENANT_SCHEMA_PATH = resolve(__dirname, '../../../../db/migrations/002_tenant.sql');

/**
 * Provision a new tenant database.
 * 1. CREATE DATABASE (via admin pool — cannot run inside a transaction)
 * 2. Apply the tenant schema (via new pool to the tenant DB)
 */
export async function provisionTenantDatabase(
  poolManager: PoolManager,
  dbName: string
): Promise<void> {
  const adminPool = poolManager.getAdminPool();

  // Check if database already exists
  const existing = await adminPool.query(
    `SELECT 1 FROM pg_database WHERE datname = $1`,
    [dbName]
  );

  if (existing.rows.length === 0) {
    // CREATE DATABASE cannot run inside a transaction
    // Sanitize dbName to prevent SQL injection (only allow alphanumeric + underscore)
    if (!/^[a-zA-Z0-9_]+$/.test(dbName)) {
      throw new Error(`Invalid database name: ${dbName}`);
    }
    await adminPool.query(`CREATE DATABASE ${dbName}`);
  }

  // Apply tenant schema
  const tenantPool = poolManager.getTenantPool(dbName);
  const schema = readFileSync(TENANT_SCHEMA_PATH, 'utf-8');
  await tenantPool.query(schema);
}

/**
 * Drop a tenant database. Use with extreme caution.
 */
export async function dropTenantDatabase(
  poolManager: PoolManager,
  dbName: string
): Promise<void> {
  // Close the tenant pool first
  await poolManager.closeTenantPool(dbName);

  const adminPool = poolManager.getAdminPool();
  if (!/^[a-zA-Z0-9_]+$/.test(dbName)) {
    throw new Error(`Invalid database name: ${dbName}`);
  }

  // Terminate active connections
  await adminPool.query(`
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = $1 AND pid <> pg_backend_pid()
  `, [dbName]);

  await adminPool.query(`DROP DATABASE IF EXISTS ${dbName}`);
}
