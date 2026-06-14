// canvas-engine · claude CLI backend
//
// Runs a one-shot completion via the local `claude` binary using the user's
// logged-in Claude subscription auth, so the vision paths need no API key.
//
// Notes:
//  - ANTHROPIC_API_KEY is removed from the child env: an empty or leaked key
//    forces the CLI into API-key auth and 401s instead of using the subscription.
//  - CLAUDE_CODE_OAUTH_TOKEN is intentionally PRESERVED. In a normal terminal
//    the CLI reads your stored login; but inside a host-managed Claude session a
//    spawned `claude` can't, and 401s. Supplying a `claude setup-token` value via
//    CLAUDE_CODE_OAUTH_TOKEN (e.g. from .env) restores subscription auth there.
//    Verified live 2026-05-24: clone + edit generate with only this token set.
//  - shell:false → args are passed as literal argv entries, so the (large)
//    open-lovable system prompt can go via --system-prompt with no escaping.
//  - The user prompt goes via stdin to avoid Windows argv-length limits on the
//    edit path (which embeds full file contents).
//  - An optional image is exposed to the Read tool via --add-dir on its folder.

import { spawn } from 'node:child_process';
import path from 'node:path';

const DEFAULT_MODEL = process.env.CANVAS_ENGINE_VISION_MODEL ?? 'sonnet';
const DEFAULT_TIMEOUT_MS = 240_000;

export interface ClaudeCliRequest {
  system: string;
  prompt: string;
  model?: string;
  /** Absolute path to an image the model should Read (enables the Read tool). */
  imagePath?: string;
  timeoutMs?: number;
}

export async function runClaudeCli(req: ClaudeCliRequest): Promise<string> {
  const args: string[] = [
    '-p',
    '--system-prompt',
    req.system,
    '--model',
    req.model ?? DEFAULT_MODEL,
    '--output-format',
    'text',
  ];

  if (req.imagePath !== undefined) {
    args.push(
      '--tools',
      'Read',
      '--allowedTools',
      'Read',
      '--add-dir',
      path.dirname(req.imagePath),
    );
  } else {
    args.push('--tools', '');
  }

  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;

  const timeoutMs = req.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  return await new Promise<string>((resolve, reject) => {
    const child = spawn('claude', args, {
      env,
      shell: false,
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`claude CLI timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on('error', (err) => {
      clearTimeout(timer);
      reject(new Error(`failed to spawn claude CLI: ${err.message}`));
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        const detail = (stderr || stdout).trim().slice(0, 400);
        reject(new Error(`claude CLI exited with code ${code}: ${detail}`));
        return;
      }
      resolve(stdout);
    });

    child.stdin.write(req.prompt);
    child.stdin.end();
  });
}
