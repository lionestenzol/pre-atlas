/**
 * Aegis Enterprise Fabric — API Middleware
 *
 * Express middleware chain: auth, tenant injection, rate limiting, request logging.
 */

import { Request, Response, NextFunction } from 'express';
import { TenantRegistry, TenantRecord } from '../tenants/tenant-registry.js';
import { RateLimiter } from './rate-limiter.js';
import { RequestLogger } from './request-logger.js';
import { generateUUID } from '../core/delta.js';

// Extend Express Request with AEF context
declare global {
  namespace Express {
    interface Request {
      tenant?: TenantRecord;
      requestId?: string;
      requestStart?: number;
    }
  }
}

const ADMIN_KEY = process.env.AEGIS_ADMIN_KEY || 'aegis-admin-default-key';

/**
 * Assigns a unique request ID and start timestamp.
 */
export function requestIdMiddleware(req: Request, _res: Response, next: NextFunction): void {
  req.requestId = generateUUID();
  req.requestStart = Date.now();
  next();
}

/**
 * Authenticates via X-API-Key header.
 * Sets req.tenant if valid tenant key.
 * Admin endpoints use AEGIS_ADMIN_KEY env var.
 */
export function authMiddleware(tenantRegistry: TenantRegistry) {
  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    // Health and metrics endpoints don't need auth
    if (req.path === '/health' || req.path === '/metrics') {
      next();
      return;
    }

    const apiKey = req.headers['x-api-key'] as string | undefined;
    if (!apiKey) {
      res.status(401).json({ error: 'Missing X-API-Key header' });
      return;
    }

    // Check admin key for tenant management
    if (req.path.startsWith('/api/v1/tenants') && req.method === 'POST') {
      if (apiKey === ADMIN_KEY) {
        next();
        return;
      }
    }

    // Check admin key for listing tenants
    if (req.path === '/api/v1/tenants' && req.method === 'GET') {
      if (apiKey === ADMIN_KEY) {
        next();
        return;
      }
    }

    // Resolve tenant from API key
    const tenant = await tenantRegistry.getTenantByApiKey(apiKey);
    if (!tenant) {
      res.status(401).json({ error: 'Invalid API key' });
      return;
    }

    if (!tenant.data.enabled) {
      res.status(403).json({ error: 'Tenant is disabled' });
      return;
    }

    req.tenant = tenant;
    next();
  };
}

/**
 * Rate limiting middleware using token bucket per tenant.
 */
export function rateLimitMiddleware(rateLimiter: RateLimiter) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.tenant) {
      next();
      return;
    }

    const agentId = (req.body?.agent_id as string) || undefined;
    const allowed = rateLimiter.consume(
      req.tenant.id,
      req.tenant.data.quotas.max_actions_per_hour,
      agentId
    );

    if (!allowed) {
      const remaining = rateLimiter.getRemaining(req.tenant.id, agentId);
      res.status(429).json({
        error: 'Rate limit exceeded',
        remaining,
        retry_after_ms: 60_000,
      });
      return;
    }

    next();
  };
}

/**
 * Response logging middleware. Must be mounted early to capture timing.
 */
export function responseLogMiddleware(requestLogger: RequestLogger) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const originalSend = res.send.bind(res);
    res.send = function (body: unknown) {
      requestLogger.log({
        timestamp: Date.now(),
        tenant_id: req.tenant?.id || null,
        agent_id: (req.body?.agent_id as string) || null,
        method: req.method,
        path: req.path,
        status_code: res.statusCode,
        duration_ms: req.requestStart ? Date.now() - req.requestStart : 0,
        request_id: req.requestId || 'unknown',
      });
      return originalSend(body);
    } as typeof res.send;
    next();
  };
}
