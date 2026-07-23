/**
 * LangGraph Skill Lattice Seq 7 (Supervisor) -- pure logic for resuming a
 * retried lattice run, split out of governance_daemon.ts so it's testable
 * without constructing a full GovernanceDaemon (Storage, cron, etc.).
 *
 * LangGraph has no auto-resume of its own (Honest Cost #2,
 * docs/LANGGRAPH_SKILL_LATTICE_PLAN.md): something external must call
 * `graph.ainvoke(None, config)` after a crash. delta-kernel's work queue is
 * that external supervisor -- WorkController.checkTimeouts() already retries
 * a timed-out job in place (fresh clock, cleared claim); this module answers
 * "is this retried job a lattice run, and if so what command resumes it."
 */

import * as fs from 'fs';
import * as path from 'path';

export interface LatticeResumeMetadata {
  kind?: string;
  thread_id?: string;
  db?: string;
  pairs?: [string, string][];
  max_turns?: number;
  max_budget_usd?: number;
  demo?: boolean;
}

export interface JobLike {
  job_id: string;
  metadata: Record<string, unknown>;
}

export function isLatticeResumeJob(job: JobLike): boolean {
  return (job.metadata as LatticeResumeMetadata | undefined)?.kind === 'lattice_resume';
}

/**
 * Picks the isolated venv Python that has langgraph/claude-agent-sdk
 * installed (the global Python deliberately doesn't -- see
 * tools/lattice/README.md's Seq 3 section for the langchain-core conflict
 * that motivated the isolation). Falls back to bare 'python' if the venv
 * isn't present, so this doesn't hard-fail in an environment without it.
 */
export function resolveLatticePython(repoRoot: string): string {
  const venvPython = path.join(repoRoot, 'services', 'atlas-map-api', '.venv', 'Scripts', 'python.exe');
  return fs.existsSync(venvPython) ? venvPython : 'python';
}

/**
 * Builds the argv for re-launching run_chain.py --resume against the same
 * thread_id/db, passing --job-id so the resumed process reports completion
 * against the SAME delta-kernel job rather than registering a second one.
 */
export function buildResumeArgs(jobId: string, meta: LatticeResumeMetadata): string[] {
  if (!meta.thread_id || !meta.db) {
    throw new Error(`lattice_resume job ${jobId} is missing thread_id/db in metadata -- cannot resume`);
  }

  const args = [
    'run_chain.py',
    '--thread-id', meta.thread_id,
    '--resume',
    '--db', meta.db,
    '--job-id', jobId,
    '--supervised',
  ];
  if (meta.max_turns) args.push('--max-turns', String(meta.max_turns));
  if (meta.max_budget_usd) args.push('--max-budget', String(meta.max_budget_usd));
  if (meta.demo) {
    args.push('--demo');
  } else {
    for (const [skill, prompt] of meta.pairs ?? []) args.push(skill, prompt);
  }
  return args;
}
