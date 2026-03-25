/**
 * @aegis-fabric/sdk
 * Thin TypeScript client for the Aegis Fabric API.
 */

export interface AegisClientOptions {
  /** Aegis API base URL (e.g., "https://aegis.example.com") */
  baseUrl: string;
  /** Tenant API key */
  apiKey: string;
  /** Request timeout in ms (default: 10000) */
  timeout?: number;
}

export interface AgentRegistration {
  name: string;
  provider: string;
  version?: string;
  capabilities: string[];
  cost_center?: string;
}

export interface ActionRequest {
  agent_id: string;
  action: string;
  params?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface PolicyDecision {
  effect: 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
  matched_rule?: string;
  reason?: string;
}

export interface ActionResponse {
  status: 'executed' | 'blocked' | 'pending_approval';
  policy_decision: PolicyDecision;
  approval_id?: string;
  expires_at?: string;
  entity_id?: string;
}

export interface PolicyRule {
  action: string;
  effect: 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
  conditions: Array<{
    field: string;
    operator: 'eq' | 'neq' | 'in' | 'not_in' | 'gt' | 'lt' | 'gte' | 'lte' | 'exists';
    value: unknown;
  }>;
  priority: number;
  enabled: boolean;
}

export class AegisError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'AegisError';
  }
}

export class AegisClient {
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;

  constructor(options: AegisClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.apiKey = options.apiKey;
    this.timeout = options.timeout ?? 10_000;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new AegisError(
          data.error || `HTTP ${res.status}`,
          res.status,
          data,
        );
      }

      return data as T;
    } finally {
      clearTimeout(timer);
    }
  }

  // --- Agents ---

  async registerAgent(agent: AgentRegistration) {
    return this.request<{ agent_id: string; name: string; status: string }>(
      'POST', '/api/v1/agents', agent,
    );
  }

  async listAgents() {
    return this.request<Array<{ agent_id: string; name: string; status: string }>>(
      'GET', '/api/v1/agents',
    );
  }

  // --- Actions (main entry point) ---

  async submitAction(action: ActionRequest): Promise<ActionResponse> {
    return this.request<ActionResponse>('POST', '/api/v1/agent/action', action);
  }

  // --- Policies ---

  async createPolicies(rules: PolicyRule[]) {
    return this.request<{ count: number }>('POST', '/api/v1/policies', { rules });
  }

  async listPolicies() {
    return this.request<{ rules: PolicyRule[] }>('GET', '/api/v1/policies');
  }

  async simulatePolicy(action: ActionRequest) {
    return this.request<{ decision: PolicyDecision; evaluated_rules: number }>(
      'POST', '/api/v1/policies/simulate', action,
    );
  }

  // --- Approvals ---

  async listApprovals() {
    return this.request<Array<{ approval_id: string; action: string; status: string }>>(
      'GET', '/api/v1/approvals',
    );
  }

  async resolveApproval(approvalId: string, decision: 'approve' | 'reject') {
    return this.request<{ status: string }>(
      'POST', `/api/v1/approvals/${approvalId}`, { decision },
    );
  }

  // --- Audit ---

  async getAuditLog() {
    return this.request<Array<Record<string, unknown>>>('GET', '/api/v1/audit');
  }

  // --- Health ---

  async health() {
    return this.request<{ status: string; uptime: number }>('GET', '/health');
  }
}
