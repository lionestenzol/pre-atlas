'use client';

import { useState, useEffect, useCallback } from 'react';
import Panel from './Panel';
import ModeTag from './ModeTag';
import { getOrchestratorStatus, executeTask } from '@/lib/api';
import type { OrchestratorStatus } from '@/lib/types';

export default function FestivalPanel() {
  const [data, setData] = useState<OrchestratorStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [execResult, setExecResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const status = await getOrchestratorStatus();
      setData(status);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Orchestrator unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleExecute = async () => {
    setExecuting(true);
    setExecResult(null);
    try {
      const result = await executeTask();
      setExecResult(result.message ?? result.status);
    } catch (e) {
      setExecResult(e instanceof Error ? e.message : 'Execute failed');
    } finally {
      setExecuting(false);
    }
  };

  const festival = data?.festival as Record<string, unknown> | undefined;

  return (
    <Panel title="Festival Manager" loading={loading} error={error} onRetry={load}>
      {data && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <ModeTag mode={data.mode} />
            <span className="text-xs text-zinc-500">Risk: {data.risk}</span>
          </div>

          {festival && typeof festival === 'object' ? (
            <FestivalProgress festival={festival} />
          ) : (
            <p className="text-sm text-zinc-500">No festival data available</p>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleExecute}
              disabled={executing}
              className="text-sm px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white font-medium disabled:opacity-50 transition-colors"
            >
              {executing ? 'Executing...' : 'Execute Next'}
            </button>
            {execResult && (
              <span className="text-xs text-zinc-400">{execResult}</span>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function FestivalProgress({ festival }: { festival: Record<string, unknown> }) {
  // The orchestrator returns festival as a nested object — render whatever keys are present
  const entries = Object.entries(festival).filter(
    ([, v]) => v != null && typeof v !== 'function'
  );

  if (entries.length === 0) {
    return <p className="text-sm text-zinc-500">No phases found</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => {
        // Try to render as progress if it has done/total shape
        const obj = value as Record<string, unknown>;
        if (typeof obj === 'object' && obj !== null && 'done' in obj && 'total' in obj) {
          const done = Number(obj.done);
          const total = Number(obj.total);
          const pct = total > 0 ? (done / total) * 100 : 0;
          return (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-zinc-400">{key}</span>
                <span className="text-zinc-500">{done}/{total}</span>
              </div>
              <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        }
        // Fallback: render as key-value
        return (
          <div key={key} className="text-xs text-zinc-400">
            <span className="text-zinc-500">{key}:</span> {String(value)}
          </div>
        );
      })}
    </div>
  );
}
