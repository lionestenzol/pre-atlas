#!/usr/bin/env npx tsx
/**
 * Gate CLI — Command-line interface to the Work Controller
 *
 * Usage:
 *   npx tsx src/tools/gate.ts request --type ai --title "Task name" --agent claude
 *   npx tsx src/tools/gate.ts complete --job_id j_xxx --outcome completed
 *   npx tsx src/tools/gate.ts status
 *   npx tsx src/tools/gate.ts cancel --job_id j_xxx
 */

import { requestWork, completeWork, getWorkStatus, cancelWork } from './gate_client.js';

const [, , command, ...args] = process.argv;

function parseArgs(args: string[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '');
    const value = args[i + 1];
    if (key && value) {
      result[key] = value;
    }
  }
  return result;
}

async function main() {
  try {
    switch (command) {
      case 'request': {
        const opts = parseArgs(args);
        if (!opts.type || !opts.title) {
          console.error('Usage: gate request --type <human|ai|system> --title "Job title" [--agent <name>] [--weight <1-10>]');
          process.exit(1);
        }
        const result = await requestWork({
          type: opts.type as 'human' | 'ai' | 'system',
          title: opts.title,
          agent: opts.agent,
          weight: opts.weight ? parseInt(opts.weight, 10) : undefined,
        });
        console.log(JSON.stringify(result, null, 2));
        break;
      }

      case 'complete': {
        const opts = parseArgs(args);
        if (!opts.job_id || !opts.outcome) {
          console.error('Usage: gate complete --job_id <id> --outcome <completed|failed|abandoned> [--error "message"]');
          process.exit(1);
        }
        const result = await completeWork({
          job_id: opts.job_id,
          outcome: opts.outcome as 'completed' | 'failed' | 'abandoned',
          error: opts.error,
        });
        console.log(JSON.stringify(result, null, 2));
        break;
      }

      case 'status': {
        const result = await getWorkStatus();
        console.log(JSON.stringify(result, null, 2));
        break;
      }

      case 'cancel': {
        const opts = parseArgs(args);
        if (!opts.job_id) {
          console.error('Usage: gate cancel --job_id <id> [--reason "message"]');
          process.exit(1);
        }
        const result = await cancelWork({
          job_id: opts.job_id,
          reason: opts.reason,
        });
        console.log(JSON.stringify(result, null, 2));
        break;
      }

      default:
        console.log(`
Gate CLI — Work Controller Interface

Commands:
  request   Request permission to start a job
  complete  Report job completion
  status    Query current work state
  cancel    Cancel a job

Examples:
  gate request --type ai --title "Summarize notes" --agent claude
  gate complete --job_id j_abc123 --outcome completed
  gate status
  gate cancel --job_id j_abc123 --reason "No longer needed"
`);
        break;
    }
  } catch (error) {
    console.error('Error:', (error as Error).message);
    process.exit(1);
  }
}

main();
