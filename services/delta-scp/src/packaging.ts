// Delta SCP · deployable package + sealed receipt
//
// Closes the gap the 2026-07-13 proof-run named: the dossier was a MAP (three
// loose JSON/markdown files), not a deliverable. This module produces the two
// things the Supagetti menu actually promised:
//   - dossier.zip       the deployable package — the 3 dossier files, one file
//                        a customer can open with no special tooling.
//   - dossier.zip.sgl    the sealed receipt — dossier.zip run through sigil's
//                        content-addressable codec (assemble-first: sigil
//                        already exists, on PATH, sha256-verified byte-identical
//                        round-trip; we do not hand-roll a sealing format).
//
// sigil unpack lets Bruke's own infra verify a delivered package matches what
// was generated (tamper-evidence via the header sha256), without requiring the
// customer to have sigil installed — they open dossier.zip directly. Sealing is
// best-effort: sigil is an external system binary (Bruke's own private tool,
// not a vendored npm/PyPI dependency), so a missing PATH entry degrades the
// receipt (sealed: false) rather than failing the whole dossier generation —
// same fail-soft-but-honest posture as collectRiskySurfaces.

import { promises as fs, createWriteStream } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { ZipArchive } from 'archiver';

const execFileAsync = promisify(execFile);

export interface PackageResult {
  zip_path: string;
  zip_bytes: number;
}

export async function bundleDeployablePackage(
  outDir: string, fileNames: string[],
): Promise<PackageResult> {
  const zipPath = path.join(outDir, 'dossier.zip');
  await new Promise<void>((resolve, reject) => {
    const output = createWriteStream(zipPath);
    const archive = new ZipArchive({ zlib: { level: 9 } });
    output.on('close', () => resolve());
    output.on('error', reject);
    archive.on('error', reject);
    archive.pipe(output);
    for (const name of fileNames) {
      archive.file(path.join(outDir, name), { name });
    }
    void archive.finalize();
  });
  const { size } = await fs.stat(zipPath);
  return { zip_path: zipPath, zip_bytes: size };
}

export interface SealResult {
  sealed: boolean;
  sealed_path?: string;
  sha256?: string;
  orig_bytes?: number;
  packed_bytes?: number;
  error?: string;
}

interface SigilPackReceipt {
  sha256: string;
  orig_bytes: number;
  packed_bytes: number;
  output: string;
}

export async function sealArtifact(filePath: string): Promise<SealResult> {
  const sealedPath = `${filePath}.sgl`;
  try {
    const { stdout } = await execFileAsync('sigil', ['pack', filePath, '-o', sealedPath]);
    const receipt = JSON.parse(stdout) as SigilPackReceipt;
    return {
      sealed: true,
      sealed_path: sealedPath,
      sha256: receipt.sha256,
      orig_bytes: receipt.orig_bytes,
      packed_bytes: receipt.packed_bytes,
    };
  } catch (e) {
    // fail-soft: sealing is an enhancement, not a precondition for the dossier —
    // a missing/broken `sigil` on this machine degrades the receipt honestly
    // (sealed: false) rather than failing the whole modernize run.
    const message = e instanceof Error ? e.message : String(e);
    return { sealed: false, error: message };
  }
}
