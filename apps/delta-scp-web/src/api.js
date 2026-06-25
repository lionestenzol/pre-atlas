// Thin client for the live delta-scp gateway (proxied at /api → :3012).
//
// The contract mirrors the production async queue: POST /jobs returns a job, and
// a job reaches a terminal state ('complete' | 'error'). The demo adapter returns
// a terminal job immediately; a real Supabase-backed queue would return 'pending'
// and require polling. submitRepo() handles BOTH: it polls GET /jobs/:id until the
// job is terminal, so this UI works unchanged against either backend.

const TERMINAL = new Set(['complete', 'error']);

async function postJob(repoUrl, apiKey) {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {}),
    },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `request failed (${res.status})`);
  }
  return data.job;
}

async function getJob(id, apiKey) {
  const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`, {
    headers: apiKey ? { authorization: `Bearer ${apiKey}` } : {},
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `request failed (${res.status})`);
  }
  return data.job;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function submitRepo(repoUrl, { apiKey = '', pollMs = 1500, timeoutMs = 180000 } = {}) {
  let job = await postJob(repoUrl, apiKey);
  const deadline = Date.now() + timeoutMs;
  while (!TERMINAL.has(job.status)) {
    if (Date.now() > deadline) throw new Error('timed out waiting for compression to finish');
    await sleep(pollMs);
    job = await getJob(job.id, apiKey);
  }
  if (job.status === 'error') {
    throw new Error(job.error_log || 'compression failed');
  }
  return job;
}

export async function checkHealth() {
  try {
    const res = await fetch('/api/healthz');
    if (!res.ok) return false;
    const data = await res.json();
    return data.ok === true;
  } catch {
    return false;
  }
}
