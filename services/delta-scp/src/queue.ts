// Delta SCP · job queue access (atomic claim + state transitions)

import type { SupabaseClient } from '@supabase/supabase-js';

export type ScpJobStatus = 'pending' | 'processing' | 'complete' | 'error';

export interface ScpJob {
  id: string;
  repo_url: string;
  status: ScpJobStatus;
  compressed_state: Record<string, unknown> | null;
  error_log: string | null;
  attempt: number;
  max_attempts: number;
  claimed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Enqueue a new compression job. Returns the created row. */
export async function enqueueJob(
  db: SupabaseClient,
  repoUrl: string,
): Promise<ScpJob> {
  const { data, error } = await db
    .from('scp_jobs')
    .insert({ repo_url: repoUrl })
    .select('*')
    .single();
  if (error) throw new Error(`enqueueJob failed: ${error.message}`);
  return data as ScpJob;
}

/**
 * Atomically claim the oldest pending job via the claim_scp_job() SQL function
 * (UPDATE ... FOR UPDATE SKIP LOCKED). Concurrency-safe: two workers never get
 * the same job. Returns null when the queue is empty.
 */
export async function claimNextJob(db: SupabaseClient): Promise<ScpJob | null> {
  const { data, error } = await db.rpc('claim_scp_job');
  if (error) throw new Error(`claimNextJob failed: ${error.message}`);
  const rows = (data ?? []) as ScpJob[];
  return rows.length > 0 ? rows[0] : null;
}

/** Mark a claimed job complete and persist its compressed output. */
export async function completeJob(
  db: SupabaseClient,
  jobId: string,
  compressedState: Record<string, unknown>,
): Promise<void> {
  const { error } = await db
    .from('scp_jobs')
    .update({ status: 'complete', compressed_state: compressedState })
    .eq('id', jobId);
  if (error) throw new Error(`completeJob failed: ${error.message}`);
}

/**
 * Mark a job failed. Re-queues (status back to 'pending') while attempts remain,
 * otherwise parks it in 'error' so it stops being retried forever.
 */
export async function failJob(
  db: SupabaseClient,
  job: ScpJob,
  err: unknown,
): Promise<void> {
  const exhausted = job.attempt >= job.max_attempts;
  const { error } = await db
    .from('scp_jobs')
    .update({
      status: exhausted ? 'error' : 'pending',
      error_log: String(err instanceof Error ? err.stack ?? err.message : err),
    })
    .eq('id', job.id);
  if (error) throw new Error(`failJob failed: ${error.message}`);
}

/** Fetch a single job by id (for the API gateway's status endpoint). */
export async function getJob(
  db: SupabaseClient,
  jobId: string,
): Promise<ScpJob | null> {
  const { data, error } = await db
    .from('scp_jobs')
    .select('*')
    .eq('id', jobId)
    .maybeSingle();
  if (error) throw new Error(`getJob failed: ${error.message}`);
  return (data as ScpJob) ?? null;
}
