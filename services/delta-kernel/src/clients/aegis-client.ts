/**
 * Aegis-Fabric TypeScript client — wraps policy engine REST API on port 3002.
 *
 * All agent actions go through Aegis for policy evaluation:
 *   POST /api/v1/agent/action → ALLOW | DENY | REQUIRE_HUMAN
 *   GET  /api/v1/approvals     → pending approval queue
 *   POST /api/v1/approvals/:id → approve/reject
 *
 * Mirrors the Python client at mosaic-orchestrator/src/mosaic/clients/aegis_client.py.
 * Zero external dependencies — uses native fetch.
 */

export type AegisDecision = 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';

export interface AegisActionResult {
  decision: AegisDecision;
  reason?: string;
  approval_id?: string;
}

export class AegisClient {
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;

  constructor(baseUrl = 'http://localhost:3002', apiKey = '', timeoutMs = 5000) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.headers = { 'Content-Type': 'application/json' };
    if (apiKey) this.headers['X-Aegis-Key'] = apiKey;
    this.timeoutMs = timeoutMs;
  }

  private async request(method: string, path: string, body?: unknown): Promise<any> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this.headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!res.ok) throw new Error(`Aegis ${method} ${path}: ${res.status} ${res.statusText}`);
    return res.json();
  }

  /** POST /api/v1/agent/action — submit an action for policy evaluation. */
  async submitAction(
    agentId: string,
    actionType: string,
    payload: Record<string, unknown>,
  ): Promise<AegisActionResult> {
    return this.request('POST', '/api/v1/agent/action', {
      agent_id: agentId,
      action: { type: actionType, payload },
    });
  }

  /** GET /api/v1/approvals — list pending human approvals. */
  async listApprovals(): Promise<any> {
    return this.request('GET', '/api/v1/approvals');
  }

  /** POST /api/v1/approvals/:id — approve or reject. */
  async resolveApproval(approvalId: string, approved: boolean, reason = ''): Promise<any> {
    return this.request('POST', `/api/v1/approvals/${approvalId}`, { approved, reason });
  }

  /** GET /health — basic health check. Returns true if reachable. */
  async health(): Promise<boolean> {
    try {
      await this.request('GET', '/health');
      return true;
    } catch {
      return false;
    }
  }
}
