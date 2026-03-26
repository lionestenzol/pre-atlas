'use client';

import { useState, useEffect, useCallback } from 'react';
import Panel from './Panel';
import { getUsage, pauseUsage } from '@/lib/api';
import type { UsageData } from '@/lib/types';

export default function UsageCounter() {
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(async () => {
    try {
      const usage = await getUsage();
      setData(usage);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Service unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handlePause = async () => {
    setToggling(true);
    try {
      await pauseUsage();
      await load();
    } catch {
      // reload to get current state regardless
      await load();
    } finally {
      setToggling(false);
    }
  };

  const pct = data ? Math.min(100, (data.ai_seconds_used / data.free_tier_seconds) * 100) : 0;

  return (
    <Panel title="AI Usage" loading={loading} error={error} onRetry={load}>
      {data && (
        <div className="space-y-4">
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-mono font-bold text-zinc-100">{data.ai_seconds_used}s</span>
            <span className="text-sm text-zinc-500">/ {data.free_tier_seconds}s</span>
          </div>

          <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-green-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="flex items-center justify-between">
            {data.paused && (
              <span className="text-xs font-medium text-amber-400 bg-amber-500/20 px-2 py-0.5 rounded">
                PAUSED
              </span>
            )}
            {!data.paused && <span />}
            <button
              onClick={handlePause}
              disabled={toggling}
              className="text-xs px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 disabled:opacity-50 transition-colors"
            >
              {toggling ? '...' : data.paused ? 'Resume' : 'Pause'}
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}
