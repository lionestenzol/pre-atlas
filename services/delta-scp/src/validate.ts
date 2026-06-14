// Delta SCP · repo URL guardrails
//
// The worker runs `git clone` on whatever URL it is fed, so an open queue is an
// SSRF vector: an attacker could aim it at internal hosts or the cloud metadata
// endpoint. This validates a repo_url before it is ever enqueued or cloned.

import path from 'node:path';
import { existsSync } from 'node:fs';
import type { ScpConfig } from './config.js';

export interface ValidationResult {
  ok: boolean;
  reason?: string;
}

const ALLOWED_SCHEMES = new Set(['https:', 'git:', 'ssh:']);

// Hosts that must never be reachable from the queue, regardless of allowlist.
const BLOCKED_HOST_EXACT = new Set([
  'localhost',
  '0.0.0.0',
  '::1',
  '[::1]',
  'metadata.google.internal',
  '169.254.169.254', // cloud metadata
]);

function isPrivateOrLoopbackIp(host: string): boolean {
  // IPv4 dotted-quad checks
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  if (m) {
    const [a, b] = [Number(m[1]), Number(m[2])];
    if (a === 127) return true; // loopback
    if (a === 10) return true; // private
    if (a === 192 && b === 168) return true; // private
    if (a === 172 && b >= 16 && b <= 31) return true; // private
    if (a === 169 && b === 254) return true; // link-local / metadata
    return false;
  }
  // IPv6 loopback / unique-local / link-local
  const h = host.replace(/^\[|\]$/g, '').toLowerCase();
  if (h === '::1') return true;
  if (h.startsWith('fc') || h.startsWith('fd')) return true; // unique-local
  if (h.startsWith('fe80')) return true; // link-local
  return false;
}

function hostAllowed(host: string, allowed: string[]): boolean {
  if (allowed.length === 0) return true;
  const h = host.toLowerCase();
  return allowed.some((a) => h === a || h.endsWith(`.${a}`));
}

function looksLikeLocalPath(repoUrl: string): boolean {
  if (repoUrl.startsWith('file://')) return true;
  // absolute paths, or relative ones that resolve to something on disk
  if (path.isAbsolute(repoUrl)) return true;
  if (/^[.~]/.test(repoUrl) && existsSync(repoUrl)) return true;
  return false;
}

// scp-like git syntax: git@github.com:owner/repo.git
function parseScpLike(repoUrl: string): { host: string } | null {
  const m = /^[^@/]+@([^:/]+):.+/.exec(repoUrl);
  return m ? { host: m[1] } : null;
}

/** Validate a repo_url against the configured guardrails. */
export function validateRepoUrl(repoUrl: string, config: ScpConfig): ValidationResult {
  const url = repoUrl.trim();
  if (!url) return { ok: false, reason: 'empty repo_url' };

  if (looksLikeLocalPath(url)) {
    return config.allowLocal
      ? { ok: true }
      : { ok: false, reason: 'local paths are disabled (set SCP_ALLOW_LOCAL=true)' };
  }

  // Resolve a hostname from either a standard URL or scp-like git syntax.
  let host: string;
  const scp = parseScpLike(url);
  if (scp) {
    host = scp.host;
  } else {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return { ok: false, reason: 'unparseable repo_url' };
    }
    if (!ALLOWED_SCHEMES.has(parsed.protocol)) {
      return { ok: false, reason: `scheme not allowed: ${parsed.protocol}` };
    }
    host = parsed.hostname;
  }

  const hostKey = host.toLowerCase();
  if (BLOCKED_HOST_EXACT.has(hostKey) || isPrivateOrLoopbackIp(hostKey)) {
    return { ok: false, reason: `host not allowed: ${host}` };
  }
  if (!hostAllowed(hostKey, config.allowedHosts)) {
    return { ok: false, reason: `host not in SCP_ALLOWED_HOSTS: ${host}` };
  }
  return { ok: true };
}
