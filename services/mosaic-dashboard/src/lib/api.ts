import type {
  UsageData,
  IdeaRegistryData,
  SimulationSummary,
  SimulationDetail,
  SimulationReport,
  OrchestratorStatus,
  UnifiedState,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    let msg = res.statusText;
    try {
      const parsed = JSON.parse(body);
      msg = parsed.error ?? parsed.message ?? body;
    } catch {
      if (body) msg = body;
    }
    if (res.status === 502) msg = 'Service unavailable — backend not running';
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

// Panel 1: AI Usage
export const getUsage = () => apiFetch<UsageData>('/api/mosaic/v1/metering/usage');
export const pauseUsage = () =>
  apiFetch<{ paused: boolean; message: string }>('/api/mosaic/v1/metering/pause', { method: 'POST' });

// Panel 2: Ideas
export const getIdeas = () => apiFetch<IdeaRegistryData>('/api/delta/ideas');

// Panel 3: Simulation
export const startSimulation = (body: {
  topic: string;
  document_text?: string;
  agent_count?: number;
  tick_count?: number;
}) =>
  apiFetch<SimulationSummary>('/api/mirofish/v1/simulations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const listSimulations = () =>
  apiFetch<{ simulations: SimulationSummary[] }>('/api/mirofish/v1/simulations');

export const getSimulation = (id: string, fromTick?: number) => {
  const qs = fromTick != null ? `?from_tick=${fromTick}` : '';
  return apiFetch<SimulationDetail>(`/api/mirofish/v1/simulations/${id}${qs}`);
};

export const getSimulationReport = (id: string) =>
  apiFetch<SimulationReport>(`/api/mirofish/v1/simulations/${id}/report`);

// Panel 4: Festival / Orchestrator
export const getOrchestratorStatus = () => apiFetch<OrchestratorStatus>('/api/mosaic/v1/status');
export const executeTask = () =>
  apiFetch<{ status: string; message?: string }>('/api/mosaic/v1/tasks/execute', { method: 'POST' });

// Panel 5: Unified State
export const getUnifiedState = () => apiFetch<UnifiedState>('/api/delta/state/unified');
