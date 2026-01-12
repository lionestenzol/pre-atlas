/**
 * Gate Client — Ambient Work Controller Access
 *
 * Phase 6A.1: Makes the work controller law ambient.
 * If kernel isn't running, it wakes up. Law is never optional.
 *
 * Usage:
 *   const { job_id } = await requestWork({ type: 'ai', title: 'Task name', agent: 'claude' })
 *   // ... do work ...
 *   await completeWork({ job_id, outcome: 'completed' })
 */

import { spawn, ChildProcess } from 'child_process';
import * as net from 'net';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API_URL = 'http://localhost:3001';
const API_PORT = 3001;
const KERNEL_CWD = path.resolve(__dirname, '../..');

// === PORT CHECK ===

async function isPortOpen(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(500);
    socket.once('error', () => {
      socket.destroy();
      resolve(false);
    });
    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.connect(port, '127.0.0.1', () => {
      socket.end();
      resolve(true);
    });
  });
}

// === KERNEL BOOTSTRAP ===

let kernelProcess: ChildProcess | null = null;

async function startKernel(): Promise<void> {
  console.log('[Gate] Starting Delta Kernel...');

  // Use npm.cmd on Windows
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

  kernelProcess = spawn(npmCmd, ['run', 'api'], {
    cwd: KERNEL_CWD,
    detached: true,
    stdio: 'ignore',
    shell: true,
  });

  kernelProcess.unref();

  // Wait for health (up to 10 seconds)
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isPortOpen(API_PORT)) {
      console.log('[Gate] Delta Kernel started');
      return;
    }
  }

  throw new Error('[Gate] Delta Kernel failed to start within 10 seconds');
}

// === GATE ENSURE ===

export async function ensureGate(): Promise<void> {
  const open = await isPortOpen(API_PORT);
  if (!open) {
    await startKernel();
  }
}

// === HTTP HELPERS ===

async function post(endpoint: string, body: unknown): Promise<unknown> {
  await ensureGate();

  const response = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(`[Gate] ${endpoint} failed: ${JSON.stringify(data)}`);
  }

  return data;
}

async function get(endpoint: string): Promise<unknown> {
  await ensureGate();

  const response = await fetch(`${API_URL}${endpoint}`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(`[Gate] ${endpoint} failed: ${JSON.stringify(data)}`);
  }

  return data;
}

// === PUBLIC API ===

export interface WorkRequest {
  job_id?: string;
  type: 'human' | 'ai' | 'system';
  title: string;
  agent?: string;
  weight?: number;
  depends_on?: string[];
  timeout_ms?: number;
  metadata?: Record<string, unknown>;
}

export interface WorkCompletion {
  job_id: string;
  outcome: 'completed' | 'failed' | 'abandoned';
  result?: unknown;
  error?: string;
  metrics?: {
    duration_ms?: number;
    tokens_used?: number;
    cost_usd?: number;
  };
}

export interface WorkCancellation {
  job_id: string;
  reason?: string;
}

/**
 * Request permission to start a job.
 * If kernel isn't running, starts it first.
 */
export async function requestWork(request: WorkRequest): Promise<unknown> {
  return post('/api/work/request', request);
}

/**
 * Report job completion.
 * If kernel isn't running, starts it first.
 */
export async function completeWork(completion: WorkCompletion): Promise<unknown> {
  return post('/api/work/complete', completion);
}

/**
 * Query current work state.
 * If kernel isn't running, starts it first.
 */
export async function getWorkStatus(): Promise<unknown> {
  return get('/api/work/status');
}

/**
 * Cancel a job.
 * If kernel isn't running, starts it first.
 */
export async function cancelWork(cancellation: WorkCancellation): Promise<unknown> {
  return post('/api/work/cancel', cancellation);
}

// === CONVENIENCE: WRAPPED EXECUTION ===

/**
 * Execute work under the gate.
 * Handles request → execute → complete lifecycle automatically.
 *
 * Usage:
 *   const result = await executeUnderGate(
 *     { type: 'ai', title: 'Summarize document', agent: 'claude' },
 *     async (job_id) => {
 *       // Your AI call here
 *       return { summary: '...' };
 *     }
 *   );
 */
export async function executeUnderGate<T>(
  request: Omit<WorkRequest, 'job_id'>,
  executor: (job_id: string) => Promise<T>,
  metrics?: { tokens_used?: number; cost_usd?: number }
): Promise<T> {
  const startTime = Date.now();

  // Request admission
  const admission = (await requestWork(request)) as {
    status: string;
    job_id?: string;
    reason?: string;
  };

  if (admission.status === 'DENIED') {
    throw new Error(`[Gate] Work denied: ${admission.reason}`);
  }

  if (admission.status === 'QUEUED') {
    throw new Error(`[Gate] Work queued (position: ${(admission as { position?: number }).position}). Try again later.`);
  }

  const job_id = admission.job_id!;

  try {
    // Execute
    const result = await executor(job_id);

    // Complete successfully
    await completeWork({
      job_id,
      outcome: 'completed',
      result,
      metrics: {
        duration_ms: Date.now() - startTime,
        ...metrics,
      },
    });

    return result;
  } catch (error) {
    // Complete with failure
    await completeWork({
      job_id,
      outcome: 'failed',
      error: (error as Error).message,
      metrics: {
        duration_ms: Date.now() - startTime,
      },
    });

    throw error;
  }
}
