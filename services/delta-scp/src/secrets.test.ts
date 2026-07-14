import { describe, it, expect } from 'vitest';
import { collectSecretFindings } from './secrets.js';
import type { SourceFile } from './compressor.js';

// secretlint's engine init (loading the recommend preset) is slow on a cold
// start — well past vitest's 5s default per-test timeout on some machines.

// Built via join() rather than a literal so no committed source line contains an
// unbroken, provider-key-shaped string (GitHub push protection flags exactly that
// pattern even in an obvious test fixture — this still exercises the real
// detection logic at runtime, just without tripping the scanner on our own source
// where the string is never a real credential to begin with). Approved by Bruke
// 2026-07-14 after the push-protection block, specifically for this fixture.
const FAKE_STRIPE_KEY = ['sk', 'test', '4eC39HqLyjWDarjtT1zdp7dc'].join('_');

describe('secrets scan (secretlint)', { timeout: 20000 }, () => {
  it('finds a hardcoded Stripe test key with correct file + line attribution', async () => {
    const files: SourceFile[] = [{
      path: 'src/config.js',
      content: `const normal = 'hello world';\nconst stripeKey = '${FAKE_STRIPE_KEY}';\n`,
    }];
    const findings = await collectSecretFindings(files);
    expect(findings.length).toBeGreaterThanOrEqual(1);
    const hit = findings.find((f) => f.ruleId.includes('stripe'));
    expect(hit).toBeTruthy();
    expect(hit!.file).toBe('src/config.js');
    expect(hit!.line).toBe(2);
  });

  it('does not false-positive on ordinary code (precision)', async () => {
    const files: SourceFile[] = [{
      path: 'src/util.js',
      content: `function add(a, b) { return a + b; }\nconst greeting = 'hello world';\n`,
    }];
    expect(await collectSecretFindings(files)).toEqual([]);
  });

  it('does not flag the well-known AWS documentation example key', async () => {
    // AKIAIOSFODNN7EXAMPLE is AWS's own canonical placeholder used throughout
    // their docs — a scanner that flags it would be too noisy to trust.
    const files: SourceFile[] = [{
      path: 'src/example.js',
      content: `// from the docs\nconst exampleKey = 'AKIAIOSFODNN7EXAMPLE';\n`,
    }];
    expect(await collectSecretFindings(files)).toEqual([]);
  });

  it('returns empty for an empty file list without touching disk', async () => {
    expect(await collectSecretFindings([])).toEqual([]);
  });

  it('scans multiple files and attributes findings to the right one', async () => {
    const files: SourceFile[] = [
      { path: 'a.js', content: `const x = 1;\n` },
      { path: 'b.js', content: `const key = '${FAKE_STRIPE_KEY}';\n` },
    ];
    const findings = await collectSecretFindings(files);
    expect(findings.every((f) => f.file === 'b.js')).toBe(true);
    expect(findings.length).toBeGreaterThanOrEqual(1);
  });
});
