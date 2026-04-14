/**
 * Aegis Enterprise Fabric — Agent Registry
 *
 * CRUD for agents per tenant. Validates capabilities against AgentActionName enum.
 */

import {
  UUID, AgentData, AgentProvider, AgentActionName, Entity,
} from '../core/types.js';
import { createEntity, generateUUID, now } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';

const VALID_ACTIONS: AgentActionName[] = [
  'create_task', 'update_task', 'complete_task', 'delete_task',
  'query_state', 'propose_delta', 'route_decision',
  'request_approval', 'get_policy_simulation', 'register_webhook',
];

export class AgentRegistry {
  private storage: AegisStorage;

  constructor(storage: AegisStorage) {
    this.storage = storage;
  }

  async registerAgent(tenantId: UUID, opts: {
    name: string;
    provider: AgentProvider;
    version?: string;
    capabilities?: AgentActionName[];
    cost_center?: string;
    metadata?: Record<string, unknown>;
  }): Promise<{ agentId: UUID; entity: Entity }> {
    // Validate capabilities
    const capabilities = opts.capabilities || VALID_ACTIONS;
    for (const cap of capabilities) {
      if (!VALID_ACTIONS.includes(cap)) {
        throw new Error(`Invalid capability: ${cap}`);
      }
    }

    // Check agent quota
    const existing = this.listAgents(tenantId);
    // Quota check happens in action-processor; here we just register

    const agentData: AgentData = {
      tenant_id: tenantId,
      name: opts.name,
      provider: opts.provider,
      version: opts.version || '1.0.0',
      capabilities,
      cost_center: opts.cost_center || 'default',
      enabled: true,
      metadata: opts.metadata || {},
      created_at: now(),
      last_active_at: now(),
    };

    const { entity, delta } = await createEntity('aegis_agent', agentData, tenantId);
    this.storage.saveEntity(tenantId, entity, agentData);
    this.storage.appendDelta(tenantId, delta);

    return { agentId: entity.entity_id, entity };
  }

  getAgent(tenantId: UUID, agentId: UUID): { entity: Entity; state: AgentData } | null {
    const result = this.storage.loadEntity<AgentData>(tenantId, agentId);
    if (!result || result.entity.entity_type !== 'aegis_agent') return null;
    return result;
  }

  listAgents(tenantId: UUID): Array<{ entity: Entity; state: AgentData }> {
    return this.storage.loadEntitiesByType<AgentData>(tenantId, 'aegis_agent');
  }

  updateAgentActivity(tenantId: UUID, agentId: UUID): void {
    const agent = this.getAgent(tenantId, agentId);
    if (!agent) return;
    agent.state.last_active_at = now();
    this.storage.saveEntity(tenantId, agent.entity, agent.state);
  }

  validateAgentCapability(tenantId: UUID, agentId: UUID, action: AgentActionName): boolean {
    const agent = this.getAgent(tenantId, agentId);
    if (!agent || !agent.state.enabled) return false;
    return agent.state.capabilities.includes(action);
  }
}
