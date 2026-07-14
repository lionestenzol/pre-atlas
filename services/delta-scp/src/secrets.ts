// Delta SCP · secrets scan
//
// Assemble-first: secretlint (MIT, actively maintained) does the actual pattern
// matching for AWS/Stripe/GitHub/Slack/private-key-etc. shaped secrets via its
// recommend preset. We do not hand-roll secret regexes — a curated ruleset that
// tracks provider format changes is exactly the kind of thing a library does
// better than a one-off pattern list, and "worse, not just later" is the wrong
// tradeoff here. See ~/.claude/rules/common/assemble-first.md.
//
// @secretlint/node's engine.executeOnFiles() takes real filesystem paths, not
// in-memory content, so the already-collected SourceFile[] (fetchSourceFilesDetailed's
// analyzable set) is written to a throwaway scratch dir, scanned, then removed —
// this keeps source.ts's clone/cleanup lifecycle untouched.
//
// Scope: this scans the AST-analyzable file set (source code + json/yaml/toml/md),
// which catches the dominant real case — a hardcoded key committed directly in
// source. Dedicated credential files (.env, .pem, private keys) use filename
// patterns rather than extensions and aren't in that set; they already surface
// honestly via modernize.ts's "coverage: N files NOT analyzed" line rather than
// being silently invisible. Extending the walk to also capture those is real,
// separate scope — a named follow-up, not something folded in here.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import type { SourceFile } from './compressor.js';

export interface SecretFinding {
  file: string; // original relative path (not the scratch-dir path)
  line: number;
  message: string;
  ruleId: string;
}

const SECRETLINT_CONFIG = {
  rules: [{ id: '@secretlint/secretlint-rule-preset-recommend' }],
};

interface SecretlintFileResult {
  filePath: string;
  messages: Array<{
    message: string;
    ruleId: string;
    loc: { start: { line: number } };
  }>;
}

export async function collectSecretFindings(files: SourceFile[]): Promise<SecretFinding[]> {
  if (!files.length) return [];
  const scratch = await fs.mkdtemp(path.join(os.tmpdir(), 'scp-secrets-'));
  try {
    await fs.writeFile(
      path.join(scratch, '.secretlintrc.json'),
      JSON.stringify(SECRETLINT_CONFIG),
    );
    const pathMap = new Map<string, string>(); // scratch abs path -> original relative path
    const filePathList: string[] = [];
    for (const f of files) {
      const abs = path.join(scratch, f.path);
      await fs.mkdir(path.dirname(abs), { recursive: true });
      await fs.writeFile(abs, f.content);
      pathMap.set(abs, f.path);
      filePathList.push(abs);
    }

    const { createEngine } = await import('@secretlint/node');
    const engine = await createEngine({ color: false, cwd: scratch, formatter: 'json' });
    const result = await engine.executeOnFiles({ filePathList });
    const parsed = JSON.parse(result.output) as SecretlintFileResult[];

    const out: SecretFinding[] = [];
    for (const fileResult of parsed) {
      const orig = pathMap.get(fileResult.filePath) ?? fileResult.filePath;
      for (const m of fileResult.messages) {
        out.push({ file: orig, line: m.loc.start.line, message: m.message, ruleId: m.ruleId });
      }
    }
    out.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);
    return out;
  } finally {
    await fs.rm(scratch, { recursive: true, force: true }).catch(() => {});
  }
}
