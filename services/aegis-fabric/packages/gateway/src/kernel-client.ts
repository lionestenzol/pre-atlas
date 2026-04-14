/**
 * Aegis Gateway — Kernel HTTP Client
 *
 * Makes internal HTTP calls from Gateway to Kernel.
 * All tenant-scoped requests include x-tenant-db header.
 */

const KERNEL_URL = process.env.KERNEL_URL || 'http://localhost:3001';

export interface KernelRequestOpts {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  tenantDb?: string;
  body?: unknown;
  query?: Record<string, string>;
}

export interface KernelResponse<T = unknown> {
  status: number;
  data: T;
  ok: boolean;
}

export async function kernelRequest<T = unknown>(opts: KernelRequestOpts): Promise<KernelResponse<T>> {
  const url = new URL(opts.path, KERNEL_URL);

  if (opts.query) {
    for (const [key, value] of Object.entries(opts.query)) {
      if (value !== undefined) url.searchParams.set(key, value);
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (opts.tenantDb) {
    headers['x-tenant-db'] = opts.tenantDb;
  }

  const response = await fetch(url.toString(), {
    method: opts.method,
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  let data: T;
  try {
    data = await response.json() as T;
  } catch {
    data = {} as T;
  }

  return {
    status: response.status,
    data,
    ok: response.ok,
  };
}

/**
 * Health check the Kernel.
 */
export async function kernelHealthCheck(): Promise<{ healthy: boolean; latencyMs: number }> {
  const start = Date.now();
  try {
    const res = await kernelRequest({ method: 'GET', path: '/health' });
    return { healthy: res.ok, latencyMs: Date.now() - start };
  } catch {
    return { healthy: false, latencyMs: Date.now() - start };
  }
}
