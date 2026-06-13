-- Migration 005: Delta SCP stale-job reaper
-- Recovers jobs orphaned by a crashed worker.
--
-- claim_scp_job() flips a job to 'processing' and stamps claimed_at. If the
-- worker then dies mid-job, nothing ever moves that row out of 'processing' —
-- the failJob() path only runs for *caught* errors, not crashes. This reaper
-- re-queues rows that have sat in 'processing' longer than timeout_secs.
--
-- attempt was already incremented at claim time, so a reaped job that has
-- exhausted max_attempts parks in 'error' instead of looping forever.
-- Call from the worker via supabase.rpc('reap_stale_scp_jobs', { timeout_secs }).

CREATE OR REPLACE FUNCTION reap_stale_scp_jobs(timeout_secs INT)
RETURNS SETOF scp_jobs AS $$
    UPDATE scp_jobs
    SET status = CASE
            WHEN attempt >= max_attempts THEN 'error'
            ELSE 'pending'
        END,
        error_log = CASE
            WHEN attempt >= max_attempts
            THEN COALESCE(error_log || E'\n', '')
                 || '[reaper] orphaned in processing > '
                 || timeout_secs || 's; max_attempts exhausted'
            ELSE error_log
        END,
        claimed_at = NULL
    WHERE status = 'processing'
      AND claimed_at IS NOT NULL
      AND claimed_at < NOW() - make_interval(secs => timeout_secs)
    RETURNING *;
$$ LANGUAGE sql;
