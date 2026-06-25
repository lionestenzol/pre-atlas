// Delta SCP · API gateway auth — shared-secret API key

import { timingSafeEqual } from 'node:crypto';
import type { Request, Response, NextFunction } from 'express';
import type { ScpConfig } from './config.js';

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

/** Extracts the presented key from `Authorization: Bearer` or `x-api-key`. */
function presentedKey(req: Request): string {
  const header = req.get('authorization');
  if (header?.toLowerCase().startsWith('bearer ')) return header.slice(7).trim();
  return (req.get('x-api-key') ?? '').trim();
}

/**
 * Returns middleware that enforces the API key. If no key is configured the
 * gateway refuses all protected requests (503) rather than running wide open.
 */
export function requireApiKey(config: ScpConfig) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!config.apiKey) {
      res.status(503).json({
        ok: false,
        error: 'gateway disabled: set SCP_API_KEY to enable the jobs API',
      });
      return;
    }
    if (!safeEqual(presentedKey(req), config.apiKey)) {
      res.status(401).json({ ok: false, error: 'invalid or missing API key' });
      return;
    }
    next();
  };
}
