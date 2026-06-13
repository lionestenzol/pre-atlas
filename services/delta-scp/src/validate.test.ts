import { describe, it, expect } from 'vitest';
import { validateRepoUrl } from './validate.js';
import type { ScpConfig } from './config.js';

const base: ScpConfig = {
  supabaseUrl: '',
  supabaseServiceKey: '',
  port: 3012,
  pollIntervalMs: 5000,
  cloneDir: '/tmp/x',
  maxFileBytes: 1024,
  reapTimeoutMs: 1000,
  reapIntervalMs: 1000,
  apiKey: 'k',
  allowedHosts: [],
  allowLocal: false,
  maxFiles: 10,
  maxTotalBytes: 1000,
};
const cfg = (over: Partial<ScpConfig> = {}): ScpConfig => ({ ...base, ...over });

describe('validateRepoUrl', () => {
  it('accepts public https / git / scp-like URLs', () => {
    expect(validateRepoUrl('https://github.com/o/r.git', cfg()).ok).toBe(true);
    expect(validateRepoUrl('git://github.com/o/r.git', cfg()).ok).toBe(true);
    expect(validateRepoUrl('git@github.com:o/r.git', cfg()).ok).toBe(true);
  });

  it('rejects loopback, private, link-local and metadata hosts', () => {
    for (const host of [
      'http://localhost/x',
      'https://127.0.0.1/x',
      'https://10.1.2.3/x',
      'https://192.168.0.1/x',
      'https://172.16.0.1/x',
      'https://169.254.169.254/latest',
      'https://metadata.google.internal/x',
      // IPv6 loopback / unique-local / link-local
      'https://[::1]/x',
      'https://[fc00::1]/x',
      'https://[fd00::1]/x',
      'https://[fe80::1]/x',
    ]) {
      expect(validateRepoUrl(host, cfg()).ok).toBe(false);
    }
  });

  it('rejects disallowed schemes', () => {
    expect(validateRepoUrl('ftp://host/x', cfg()).ok).toBe(false);
    expect(validateRepoUrl('http://example.com/x', cfg()).ok).toBe(false); // http not allowed
  });

  it('enforces SCP_ALLOWED_HOSTS allowlist (with subdomain match)', () => {
    const c = cfg({ allowedHosts: ['github.com'] });
    expect(validateRepoUrl('https://github.com/o/r.git', c).ok).toBe(true);
    expect(validateRepoUrl('https://codeload.github.com/o/r', c).ok).toBe(true);
    expect(validateRepoUrl('https://gitlab.com/o/r.git', c).ok).toBe(false);
  });

  it('gates local paths behind allowLocal', () => {
    expect(validateRepoUrl('/etc/passwd', cfg()).ok).toBe(false);
    expect(validateRepoUrl('/some/repo', cfg({ allowLocal: true })).ok).toBe(true);
    expect(validateRepoUrl('file:///some/repo', cfg({ allowLocal: true })).ok).toBe(true);
  });

  it('rejects empty / unparseable input', () => {
    expect(validateRepoUrl('', cfg()).ok).toBe(false);
    expect(validateRepoUrl('not a url', cfg()).ok).toBe(false);
  });
});
