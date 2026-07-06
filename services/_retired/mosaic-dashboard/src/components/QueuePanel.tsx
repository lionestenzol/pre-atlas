'use client';

import { useState, useEffect, useCallback } from 'react';
import Panel from './Panel';
import { getQueueStats } from '@/lib/api';
import { onTaskCompleted } from '@/lib/websocket';
import type { QueueStats } from '@/lib/types';

const STATUS_COLORS: Record<string, string> = {
  pending: 'text-amber-400 bg-amber-500/20',
  claimed: 'text-blue-400 bg-blue-500/20',
  running: 'text-blue-400 bg-blue-500/20',
  completed: 'text-emerald-400 bg-emerald-500/20',
  failed: 'text-red-400 bg-red-500/20',
  dead: 'text-zinc-400 bg-zinc-500/20',
};

export default function QueuePanel() {
  const [data, setData] = useState<QueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const stats = await getQueueStats();
      setData(stats);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Service unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  // Refresh on WebSocket task.completed events
  useEffect(() => {
    const unsub = onTaskCompleted(() => { load(); });
    return unsub;
  }, [load]);

  if (data && !data.enabled) {
    return (
      <Panel title="Execution Queue" loading={false} error={null} onRetry={load}>
        <p className="text-sm text-zinc-500">Direct execution mode</p>
      </Panel>
    );
  }

  const pending = data?.stats?.pending ?? 0;
  const running = (data?.stats?.claimed ?? 0) + (data?.stats?.running ?? 0);
  const completed = data?.stats?.completed ?? 0;
  const failed = (data?.stats?.failed ?? 0) + (data?.stats?.dead ?? 0);
  const total = pending + running + completed + failed;

  return (
    <Panel title="Execution Queue" loading={loading} error={error} onRetry={load}>
      {data && (
        <div className="space-y-4">
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-mono font-bold text-zinc-100">
              {pending > 0 ? pending : running > 0 ? running : '0'}
            </span>
            <span className="text-sm text-zinc-500">
              {pending > 0 ? 'pending' : running > 0 ? 'running' : 'idle'}
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            {Object.entries(data.stats).map(([status, count]) => (
              count > 0 && (
                <span
                  key={status}
                  className={`text-xs font-medium px-2 py-0.5 rounded ${STATUS_COLORS[status] ?? 'text-zinc-400 bg-zinc-500/20'}`}
                >
                  {status}: {count}
                </span>
              )
            ))}
            {total === 0 && (
              <span className="text-xs text-zinc-600">No jobs</span>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
