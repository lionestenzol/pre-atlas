'use client';

import { useCallback, useEffect, useState } from 'react';
import ModeTag from './ModeTag';
import { onModeChanged, onLoopClosed, isConnected } from '../lib/websocket';

interface Approval {
  approval_id: string;
  action: string;
  agent_id: string;
  params: Record<string, unknown>;
  requested_at: number;
  expires_at: number;
}

interface DailyBrief {
  ok: boolean;
  mode: string;
  risk: string;
  build_allowed: boolean;
  primary_action: string;
  closure: { ratio: number; open: number };
  leverage_moves: string[];
  decisions: string[];
  lanes: Array<{ id?: string; name: string; status: string }>;
  directive: string;
  brief_generated: string | null;
}

const TENANT_KEY = process.env.NEXT_PUBLIC_AEGIS_TENANT_KEY || '';

const RISK_COLORS: Record<string, string> = {
  HIGH: 'text-red-400',
  MEDIUM: 'text-amber-400',
  LOW: 'text-green-400',
};

export default function CockpitPanel() {
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    const errors: string[] = [];

    // Fetch daily brief from delta-kernel
    try {
      const res = await fetch('/api/delta/daily-brief');
      if (res.ok) {
        setBrief(await res.json());
      } else {
        errors.push('Delta-kernel offline');
      }
    } catch {
      errors.push('Delta-kernel unreachable');
    }

    // Fetch pending approvals from aegis
    try {
      const res = await fetch('/api/aegis/v1/approvals', {
        headers: { 'X-API-Key': TENANT_KEY },
      });
      if (res.ok) {
        const data = await res.json();
        setApprovals(data.pending || []);
      }
    } catch {
      // Aegis offline is non-fatal — just no approvals
    }

    setError(errors.length > 0 ? errors.join('. ') : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();

    // Polling fallback — 30s if WebSocket not connected, 120s if connected
    const interval = setInterval(() => {
      fetchAll();
    }, isConnected() ? 120_000 : 30_000);

    // Real-time subscriptions via WebSocket
    const unsubMode = onModeChanged(() => {
      fetchAll(); // Refetch full brief on mode change
    });

    const unsubLoop = onLoopClosed(() => {
      fetchAll(); // Refetch when loop closed (closure ratio changed)
    });

    return () => {
      clearInterval(interval);
      unsubMode();
      unsubLoop();
    };
  }, [fetchAll]);

  const handleDecision = async (approvalId: string, decision: 'APPROVED' | 'REJECTED') => {
    setActing(approvalId);
    try {
      await fetch(`/api/aegis/v1/approvals/${approvalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': TENANT_KEY },
        body: JSON.stringify({ decision, reason: `Cockpit ${decision.toLowerCase()}` }),
      });
      await fetchAll();
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="col-span-full bg-zinc-900 border border-zinc-800 rounded-xl p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-zinc-800 rounded w-48" />
          <div className="h-4 bg-zinc-800 rounded w-96" />
          <div className="h-4 bg-zinc-800 rounded w-72" />
        </div>
      </div>
    );
  }

  if (error && !brief) {
    return (
      <div className="col-span-full bg-zinc-900 border border-zinc-800 rounded-xl p-8">
        <h2 className="text-lg font-semibold text-zinc-100 mb-2">Morning Cockpit</h2>
        <p className="text-red-400 text-sm">{error}</p>
        <p className="text-zinc-500 text-xs mt-2">Start delta-kernel: <code className="text-zinc-400">cd services/delta-kernel && npm run api</code></p>
        <button onClick={fetchAll} className="mt-3 text-xs text-zinc-400 hover:text-zinc-200 underline">Retry</button>
      </div>
    );
  }

  const b = brief!;
  const stale = b.brief_generated
    ? (Date.now() - new Date(b.brief_generated).getTime()) > 24 * 60 * 60 * 1000
    : true;

  return (
    <div className="col-span-full bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-6">

      {/* === ROW 1: Mode + Risk + Closure === */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <ModeTag mode={b.mode as any} large />
          <span className={`text-sm font-medium ${RISK_COLORS[b.risk] || 'text-zinc-400'}`}>
            {b.risk} RISK
          </span>
          {!b.build_allowed && (
            <span className="text-xs bg-red-900/40 text-red-400 border border-red-800 px-2 py-1 rounded">
              BUILD BLOCKED
            </span>
          )}
        </div>
        <div className="flex gap-6 text-sm">
          <div>
            <span className="text-zinc-500">Open Loops</span>
            <span className="ml-2 font-mono font-bold text-zinc-100">{b.closure.open}</span>
          </div>
          <div>
            <span className="text-zinc-500">Closure</span>
            <span className="ml-2 font-mono font-bold text-zinc-100">{b.closure.ratio}%</span>
          </div>
          {stale && (
            <span className="text-xs text-amber-500 self-center">Brief stale &gt; 24h</span>
          )}
        </div>
      </div>

      {/* === ROW 2: Pending Approvals (if any) === */}
      {approvals.length > 0 && (
        <div className="border border-amber-700/50 bg-amber-950/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-amber-400 mb-3">
            Pending Approval{approvals.length > 1 ? 's' : ''} ({approvals.length})
          </h3>
          {approvals.map((a) => (
            <div key={a.approval_id} className="flex items-center justify-between gap-4 mb-2 last:mb-0">
              <div className="flex items-center gap-2 text-sm">
                {a.params.old_mode && a.params.new_mode && (
                  <>
                    <ModeTag mode={a.params.old_mode as any} />
                    <span className="text-zinc-500">&rarr;</span>
                    <ModeTag mode={a.params.new_mode as any} />
                  </>
                )}
                {a.params.reason && (
                  <span className="text-zinc-400 text-xs italic ml-2">{String(a.params.reason)}</span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleDecision(a.approval_id, 'APPROVED')}
                  disabled={acting === a.approval_id}
                  className="bg-emerald-700 hover:bg-emerald-600 disabled:bg-zinc-700 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleDecision(a.approval_id, 'REJECTED')}
                  disabled={acting === a.approval_id}
                  className="bg-red-800 hover:bg-red-700 disabled:bg-zinc-700 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* === ROW 3: Directive + Leverage Moves === */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Directive */}
        <div>
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Today&apos;s Directive</h3>
          <p className="text-zinc-200 font-medium">{b.directive}</p>
        </div>

        {/* Leverage Moves */}
        <div>
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Top Moves</h3>
          <ol className="space-y-1.5">
            {b.leverage_moves.map((move, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="text-zinc-500 font-mono">{i + 1}.</span>
                <span className="text-zinc-200">{move}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* === ROW 4: Lanes === */}
      {b.lanes.length > 0 && (
        <div>
          <h3 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Active Lanes</h3>
          <div className="flex gap-3">
            {b.lanes.map((lane, i) => (
              <div key={lane.id || i} className="bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-sm flex-1">
                <div className="font-medium text-zinc-200">{lane.name}</div>
                <div className="text-xs text-zinc-500 mt-0.5">{lane.status}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
