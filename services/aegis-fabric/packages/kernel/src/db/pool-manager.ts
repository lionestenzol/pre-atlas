/**
 * Delta Kernel — PostgreSQL Pool Manager
 *
 * Manages per-tenant database connection pools (separate DB per tenant).
 * Admin pool connects to aegis_admin for tenant registry operations.
 */

import pg from 'pg';
const { Pool } = pg;
type PoolType = InstanceType<typeof Pool>;

export interface PoolManagerConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  adminDb: string;
  maxPoolSize: number;
}

const DEFAULT_CONFIG: PoolManagerConfig = {
  host: process.env.PGHOST || 'localhost',
  port: Number(process.env.PGPORT) || 5432,
  user: process.env.PGUSER || 'aegis',
  password: process.env.PGPASSWORD || 'aegis_dev_pass',
  adminDb: process.env.PGDATABASE || 'aegis_admin',
  maxPoolSize: Number(process.env.PG_POOL_MAX) || 10,
};

export class PoolManager {
  private config: PoolManagerConfig;
  private adminPool: PoolType;
  private tenantPools: Map<string, PoolType> = new Map();

  constructor(config?: Partial<PoolManagerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.adminPool = new Pool({
      host: this.config.host,
      port: this.config.port,
      user: this.config.user,
      password: this.config.password,
      database: this.config.adminDb,
      max: this.config.maxPoolSize,
    });
  }

  /**
   * Get the admin pool (aegis_admin database) for tenant registry operations.
   */
  getAdminPool(): PoolType {
    return this.adminPool;
  }

  /**
   * Get or create a connection pool for a specific tenant database.
   * Pools are lazily created and cached.
   */
  getTenantPool(dbName: string): PoolType {
    let pool = this.tenantPools.get(dbName);
    if (pool) return pool;

    pool = new Pool({
      host: this.config.host,
      port: this.config.port,
      user: this.config.user,
      password: this.config.password,
      database: dbName,
      max: this.config.maxPoolSize,
    });

    this.tenantPools.set(dbName, pool);
    return pool;
  }

  /**
   * Close a specific tenant pool.
   */
  async closeTenantPool(dbName: string): Promise<void> {
    const pool = this.tenantPools.get(dbName);
    if (pool) {
      await pool.end();
      this.tenantPools.delete(dbName);
    }
  }

  /**
   * Close all pools (admin + all tenants). Call on graceful shutdown.
   */
  async closeAll(): Promise<void> {
    await this.adminPool.end();
    for (const [, pool] of this.tenantPools) {
      await pool.end();
    }
    this.tenantPools.clear();
  }

  /**
   * Health check: verify admin pool connectivity.
   */
  async healthCheck(): Promise<{ connected: boolean; latencyMs: number }> {
    const start = Date.now();
    try {
      await this.adminPool.query('SELECT 1');
      return { connected: true, latencyMs: Date.now() - start };
    } catch {
      return { connected: false, latencyMs: Date.now() - start };
    }
  }

  /**
   * Get count of active tenant pools.
   */
  getPoolCount(): number {
    return this.tenantPools.size;
  }
}
