import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { bundleDeployablePackage, sealArtifact } from './packaging.js';

describe('packaging · deployable zip + sealed receipt', () => {
  it('bundles named files into a real zip a customer can open', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-pkg-'));
    try {
      await fs.writeFile(path.join(dir, 'MODERNIZATION_REPORT.md'), '# hello\n');
      await fs.writeFile(path.join(dir, 'symbolic_map.json'), '{"a":1}');
      const result = await bundleDeployablePackage(dir, ['MODERNIZATION_REPORT.md', 'symbolic_map.json']);
      expect(result.zip_bytes).toBeGreaterThan(0);
      await expect(fs.stat(result.zip_path)).resolves.toBeTruthy();
      // real zip magic bytes (PK\x03\x04), not an empty/corrupt stub
      const head = await fs.readFile(result.zip_path);
      expect(head.subarray(0, 2).toString('latin1')).toBe('PK');
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });

  it('seals a file via sigil and the receipt sha256 matches an independent hash of the source file', async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-seal-'));
    try {
      const target = path.join(dir, 'payload.bin');
      const content = Buffer.from('deterministic dossier content for sealing\n');
      await fs.writeFile(target, content);

      const result = await sealArtifact(target);
      expect(result.sealed).toBe(true);
      expect(result.sha256).toMatch(/^[0-9a-f]{64}$/);
      await expect(fs.stat(result.sealed_path!)).resolves.toBeTruthy();

      const { createHash } = await import('node:crypto');
      const expected = createHash('sha256').update(content).digest('hex');
      expect(result.sha256).toBe(expected);
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });

  it('sealing degrades gracefully (sealed:false) rather than throwing when the target does not exist', async () => {
    const result = await sealArtifact('C:/definitely/not/a/real/path/nope.zip');
    expect(result.sealed).toBe(false);
    expect(result.error).toBeTruthy();
  });
});
