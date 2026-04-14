'use client';

import { useCallback, useEffect, useState } from 'react';
import Panel from './Panel';
import ModeTag from './ModeTag';

interface Approval {
  approval_id: string;
  action: string;
  agent_id: string;
  params: {
    new_mode?: string;
    old_mode?: string;
    closure_ratio?: number;
    open_loops?: number;
    reason?: string;
  };
  requested_at: number;
  expires_at: number;
}

const TENANT_KEY = process.env.NEXT_PUBLIC_AEGIS_TENANT_KEY || '';

export default function ApprovalPanel() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      const res = await fetch('/api/aegis/v1/approvals', {
        headers: { 'X-API-Key': TENANT_KEY },
      });
      if (!res.ok) {
        setError(res.status === 502 ? 'Aegis offline' : `Error ${res.status}`);
        setApprovals([]);
        return;
      }
      const data = await res.json();
      setApprovals(data.pending || []);
      setError(null);
    } catch {
      setError('Cannot reach aegis');
      setApprovals([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 30_000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  const handleDecision = async (approvalId: string, decision: 'APPROVED' | 'REJECTED') => {
    setActing(approvalId);
    try {
      await fetch(`/api/aegis/v1/approvals/${approvalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': TENANT_KEY },
        body: JSON.stringify({ decision, reason: `Dashboard ${decision.toLowerCase()} at ${new Date().toISOString()}` }),
      });
      await fetchApprovals();
    } catch {
      setError('Failed to submit decision');
    } finally {
      setActing(null);
    }
  };

  const isStale = (requestedAt: number) => Date.now() - requestedAt > 24 * 60 * 60 * 1000;

  return (
    <Panel
      title={`Governance Approvals${approvals.length > 0 ? ` (${approvals.length})` : ''}`}
      loading={loading}
      error={error}
      onRetry={fetchApprovals}
    >
      {approvals.length === 0 ? (
        <p className="text-zinc-500 text-sm">No pending approvals</p>
      ) : (
        <div className="space-y-4">
          {approvals.map((a) => (
            <div
              key={a.approval_id}
              className={`border rounded-lg p-4 ${
                isStale(a.requested_at)
                  ? 'border-amber-600 bg-amber-950/20'
                  : 'border-zinc-700 bg-zinc-800/50'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-400 uppercase tracking-wide">
                  {a.action.replace(/_/g, ' ')}
                </span>
                {isStale(a.requested_at) && (
                  <span className="text-xs text-amber-400">Stale &gt; 24h</span>
                )}
              </div>

              {a.params.old_mode && a.params.new_mode && (
                <div className="flex items-center gap-2 mb-3">
                  <ModeTag mode={a.params.old_mode} />
                  <span className="text-zinc-500">&rarr;</span>
                  <ModeTag mode={a.params.new_mode} />
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400 mb-3">
                {a.params.closure_ratio != null && (
                  <div>Closure: {a.params.closure_ratio}%</div>
                )}
                {a.params.open_loops != null && (
                  <div>Open loops: {a.params.open_loops}</div>
                )}
              </div>

              {a.params.reason && (
                <p className="text-xs text-zinc-400 mb-3 italic">{a.params.reason}</p>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => handleDecision(a.approval_id, 'APPROVED')}
                  disabled={acting === a.approval_id}
                  className="flex-1 bg-emerald-700 hover:bg-emerald-600 disabled:bg-zinc-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  {acting === a.approval_id ? '...' : 'Approve'}
                </button>
                <button
                  onClick={() => handleDecision(a.approval_id, 'REJECTED')}
                  disabled={acting === a.approval_id}
                  className="flex-1 bg-red-800 hover:bg-red-700 disabled:bg-zinc-700 text-white text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
