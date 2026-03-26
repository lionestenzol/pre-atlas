'use client';

import { useState, useEffect, useCallback } from 'react';
import Panel from './Panel';
import ModeTag from './ModeTag';
import { getUnifiedState } from '@/lib/api';
import type { UnifiedDerived } from '@/lib/types';

const REFRESH_MS = 30_000;

export default function ModePanel() {
  const [derived, setDerived] = useState<UnifiedDerived | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getUnifiedState();
      setDerived(data.derived);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load state');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <Panel title="Mode & Governance" loading={loading} error={error} onRetry={load}>
      {derived && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <ModeTag mode={derived.mode} large />
            <span className={`text-sm font-medium ${derived.build_allowed ? 'text-green-400' : 'text-red-400'}`}>
              {derived.build_allowed ? 'Build Allowed' : 'Build Blocked'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="Risk" value={derived.risk} />
            <Stat label="Open Loops" value={derived.open_loops} />
            <Stat label="Closure Ratio" value={`${(derived.closure_ratio * 100).toFixed(0)}%`} />
            <Stat label="Streak" value={`${derived.streak_days}d`} />
            <Stat label="Closures Today" value={derived.closures_today} />
            <Stat label="Violations" value={derived.violations_count} />
          </div>

          <p className="text-xs text-zinc-500">Auto-refreshes every 30s</p>
        </div>
      )}
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-zinc-800/50 rounded-lg px-3 py-2">
      <div className="text-zinc-500 text-xs">{label}</div>
      <div className="text-zinc-100 font-mono font-semibold">{value}</div>
    </div>
  );
}
