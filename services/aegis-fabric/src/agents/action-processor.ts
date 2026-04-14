/**
 * Aegis Enterprise Fabric — Action Processor
 *
 * Main pipeline for processing agent actions:
 * validate → policy check → execute/deny/queue approval → track usage → emit events
 */

import {
  UUID, CanonicalAgentAction, ActionResponse, PolicyEvaluationContext,
  AegisTaskData, Entity, JsonPatch,
} from '../core/types.js';
import { createEntity, createDelta, generateUUID, now } from '../core/delta.js';
import { AegisStorage } from '../storage/aegis-storage.js';
import { AgentRegistry } from './agent-registry.js';
import { PolicyEngine } from '../policies/policy-engine.js';
import { ApprovalQueue } from '../approval/approval-queue.js';
import { TenantRegistry } from '../tenants/tenant-registry.js';

export class ActionProcessor {
  private storage: AegisStorage;
  private agentRegistry: AgentRegistry;
  private policyEngine: PolicyEngine;
  private approvalQueue: ApprovalQueue;
  private tenantRegistry: TenantRegistry;
  private eventHandler?: (event: string, data: unknown) => void;
  private usageHandler?: (tenantId: UUID, agentId: UUID, action: string, tokens?: number, cost?: number) => void;

  constructor(opts: {
    storage: AegisStorage;
    agentRegistry: AgentRegistry;
    policyEngine: PolicyEngine;
    approvalQueue: ApprovalQueue;
    tenantRegistry: TenantRegistry;
  }) {
    this.storage = opts.storage;
    this.agentRegistry = opts.agentRegistry;
    this.policyEngine = opts.policyEngine;
    this.approvalQueue = opts.approvalQueue;
    this.tenantRegistry = opts.tenantRegistry;
  }

  onEvent(handler: (event: string, data: unknown) => void): void {
    this.eventHandler = handler;
  }

  onUsage(handler: (tenantId: UUID, agentId: UUID, action: string, tokens?: number, cost?: number) => void): void {
    this.usageHandler = handler;
  }

  async process(action: CanonicalAgentAction): Promise<ActionResponse> {
    const { tenant_id, agent_id } = action;

    // 1. Validate agent exists and has capability
    const agent = this.agentRegistry.getAgent(tenant_id, agent_id);
    if (!agent) {
      return this.deny(action, 'Agent not found');
    }
    if (!agent.state.enabled) {
      return this.deny(action, 'Agent is disabled');
    }
    if (!agent.state.capabilities.includes(action.action)) {
      return this.deny(action, `Agent lacks capability: ${action.action}`);
    }

    // 2. Get tenant for policy context
    const tenant = this.tenantRegistry.getTenant(tenant_id);
    if (!tenant) {
      return this.deny(action, 'Tenant not found');
    }

    // 3. Evaluate policy
    const policyContext: PolicyEvaluationContext = {
      tenant: { id: tenant_id, tier: tenant.data.tier, mode: tenant.data.mode },
      agent: { id: agent_id, provider: agent.state.provider, capabilities: agent.state.capabilities },
      action: action.action,
      params: action.params,
      mode: tenant.data.mode,
    };

    const decision = this.policyEngine.evaluate(policyContext);

    // 4. Handle policy decision
    if (decision.effect === 'DENY') {
      this.emit('action.denied', { action, decision });
      this.trackUsage(action);
      return {
        status: 'denied',
        action_id: action.action_id,
        policy_decision: {
          effect: 'DENY',
          matched_rule: decision.matched_rule_id,
          reason: decision.reason,
          cached: decision.cached,
        },
      };
    }

    if (decision.effect === 'REQUIRE_HUMAN') {
      const { approvalId } = await this.approvalQueue.submit(action);
      this.emit('approval.requested', { action, decision, approvalId });
      this.trackUsage(action);
      return {
        status: 'pending_approval',
        action_id: action.action_id,
        policy_decision: {
          effect: 'REQUIRE_HUMAN',
          matched_rule: decision.matched_rule_id,
          reason: decision.reason,
          cached: decision.cached,
        },
        approval: {
          approval_id: approvalId,
          status: 'PENDING',
          expires_at: now() + 3_600_000,
        },
      };
    }

    // 5. Execute the action
    const result = await this.executeAction(action);

    // 6. Track usage and emit event
    this.trackUsage(action);
    this.emit('action.completed', { action, result });

    // Update agent activity timestamp
    this.agentRegistry.updateAgentActivity(tenant_id, agent_id);

    return {
      status: 'executed',
      action_id: action.action_id,
      result,
      policy_decision: {
        effect: 'ALLOW',
        matched_rule: decision.matched_rule_id,
        reason: decision.reason,
        cached: decision.cached,
      },
    };
  }

  // === ACTION EXECUTORS ===

  private async executeAction(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    switch (action.action) {
      case 'create_task':
        return this.executeCreateTask(action);
      case 'update_task':
        return this.executeUpdateTask(action);
      case 'complete_task':
        return this.executeCompleteTask(action);
      case 'delete_task':
        return this.executeDeleteTask(action);
      case 'query_state':
        return this.executeQueryState(action);
      case 'route_decision':
        return this.executeRouteDecision(action);
      default:
        return this.executeGenericDelta(action);
    }
  }

  private async executeCreateTask(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const params = action.params;
    const taskData: AegisTaskData = {
      tenant_id: action.tenant_id,
      title: (params.title as string) || 'Untitled Task',
      description: (params.description as string) || '',
      status: 'OPEN',
      priority: (params.priority as 1|2|3|4|5) || 3,
      tags: (params.tags as string[]) || [],
      assignee: (params.assignee as string) || null,
      approval_required: false,
      approval_status: 'NOT_REQUIRED',
      due_at: (params.due_at as number) || null,
      linked_entities: [],
      metadata: (params.metadata as Record<string, unknown>) || {},
      created_by: action.agent_id,
      created_at: now(),
      updated_at: now(),
    };

    const { entity, delta } = await createEntity('aegis_task', taskData, action.tenant_id);
    this.storage.saveEntity(action.tenant_id, entity, taskData);
    this.storage.appendDelta(action.tenant_id, delta);

    return { entity_id: entity.entity_id, delta_id: delta.delta_id, state: taskData };
  }

  private async executeUpdateTask(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const taskId = action.params.task_id as string;
    if (!taskId) throw new Error('task_id required for update_task');

    const existing = this.storage.loadEntity<AegisTaskData>(action.tenant_id, taskId);
    if (!existing) throw new Error(`Task not found: ${taskId}`);

    const updates = action.params.updates as Record<string, unknown> || action.params;
    const patch: JsonPatch[] = [];

    for (const [key, value] of Object.entries(updates)) {
      if (key === 'task_id' || key === 'updates') continue;
      patch.push({ op: 'replace', path: `/${key}`, value });
    }
    patch.push({ op: 'replace', path: '/updated_at', value: now() });

    const { entity, delta, state } = await createDelta(
      existing.entity, existing.state as unknown as Record<string, unknown>, patch, 'agent', action.tenant_id
    );
    this.storage.saveEntity(action.tenant_id, entity, state);
    this.storage.appendDelta(action.tenant_id, delta);

    return { entity_id: entity.entity_id, delta_id: delta.delta_id, state };
  }

  private async executeCompleteTask(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const taskId = action.params.task_id as string;
    if (!taskId) throw new Error('task_id required for complete_task');

    const existing = this.storage.loadEntity<AegisTaskData>(action.tenant_id, taskId);
    if (!existing) throw new Error(`Task not found: ${taskId}`);

    const patch: JsonPatch[] = [
      { op: 'replace', path: '/status', value: 'DONE' },
      { op: 'replace', path: '/updated_at', value: now() },
    ];

    const { entity, delta, state } = await createDelta(
      existing.entity, existing.state as unknown as Record<string, unknown>, patch, 'agent', action.tenant_id
    );
    this.storage.saveEntity(action.tenant_id, entity, state);
    this.storage.appendDelta(action.tenant_id, delta);

    this.emit('task.completed', { tenant_id: action.tenant_id, task_id: taskId });

    return { entity_id: entity.entity_id, delta_id: delta.delta_id, state };
  }

  private async executeDeleteTask(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const taskId = action.params.task_id as string;
    if (!taskId) throw new Error('task_id required for delete_task');

    const existing = this.storage.loadEntity<AegisTaskData>(action.tenant_id, taskId);
    if (!existing) throw new Error(`Task not found: ${taskId}`);

    const patch: JsonPatch[] = [
      { op: 'replace', path: '/status', value: 'ARCHIVED' },
      { op: 'replace', path: '/updated_at', value: now() },
    ];

    const { entity, delta, state } = await createDelta(
      existing.entity, existing.state as unknown as Record<string, unknown>, patch, 'agent', action.tenant_id
    );
    this.storage.saveEntity(action.tenant_id, entity, state);
    this.storage.appendDelta(action.tenant_id, delta);

    return { entity_id: entity.entity_id, delta_id: delta.delta_id, state };
  }

  private async executeQueryState(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const entityId = action.params.entity_id as string;
    if (entityId) {
      const result = this.storage.loadEntity(action.tenant_id, entityId);
      return {
        entity_id: entityId,
        delta_id: 'query',
        state: result ? result.state : null,
      };
    }

    // List entities by type
    const entityType = action.params.entity_type as string;
    if (entityType) {
      const results = this.storage.loadEntitiesByType(action.tenant_id, entityType as any);
      return {
        entity_id: 'query',
        delta_id: 'query',
        state: results.map(r => ({ entity_id: r.entity.entity_id, ...r.state as object })),
      };
    }

    // Return stats
    const stats = this.storage.getStats(action.tenant_id);
    return { entity_id: 'query', delta_id: 'query', state: stats };
  }

  private async executeRouteDecision(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    const { new_mode, old_mode, closure_ratio, open_loops, reason } = action.params as Record<string, unknown>;

    // Apply mode change to delta-kernel via HTTP
    const DELTA_KERNEL_URL = process.env.DELTA_KERNEL_URL || 'http://localhost:3001';
    const payload = {
      run_id: `aegis-route-${Date.now()}`,
      cognitive: {
        state: {},
        loops: [],
        drift: {},
        closure: { open: open_loops ?? 0, closed: 0, ratio: closure_ratio ?? 0 },
      },
      directive: {
        mode: new_mode,
        mode_source: 'aegis-fabric',
        build_allowed: ['BUILD', 'COMPOUND', 'SCALE'].includes(String(new_mode)),
        primary_action: reason || `Mode transition: ${old_mode} -> ${new_mode}`,
        open_loop_count: open_loops ?? 0,
        closure_ratio: closure_ratio ?? 0,
        risk: (['CLOSURE'].includes(String(new_mode)) ? 'HIGH' : 'MEDIUM'),
        schema_version: '1.0.0',
      },
    };

    try {
      const resp = await fetch(`${DELTA_KERNEL_URL}/api/ingest/cognitive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await resp.json() as Record<string, unknown>;

      this.emit('tenant.mode_changed', {
        tenant_id: action.tenant_id,
        old_mode,
        new_mode,
        applied_to_delta_kernel: result.success ?? false,
      });

      return {
        entity_id: 'route_decision',
        delta_id: generateUUID(),
        state: {
          action: 'route_decision',
          old_mode,
          new_mode,
          delta_kernel_response: result,
          applied_at: now(),
        },
      };
    } catch (err) {
      return {
        entity_id: 'route_decision',
        delta_id: generateUUID(),
        state: {
          action: 'route_decision',
          old_mode,
          new_mode,
          error: String(err),
          applied_at: now(),
        },
      };
    }
  }

  private async executeGenericDelta(action: CanonicalAgentAction): Promise<{ entity_id: UUID; delta_id: UUID; state: unknown }> {
    // Generic handler for propose_delta, route_decision, etc.
    return {
      entity_id: 'generic',
      delta_id: generateUUID(),
      state: { action: action.action, params: action.params, processed_at: now() },
    };
  }

  // === HELPERS ===

  private deny(action: CanonicalAgentAction, reason: string): ActionResponse {
    return {
      status: 'denied',
      action_id: action.action_id,
      policy_decision: {
        effect: 'DENY',
        matched_rule: null,
        reason,
        cached: false,
      },
    };
  }

  private emit(event: string, data: unknown): void {
    if (this.eventHandler) {
      this.eventHandler(event, data);
    }
  }

  private trackUsage(action: CanonicalAgentAction): void {
    if (this.usageHandler) {
      this.usageHandler(
        action.tenant_id,
        action.agent_id,
        action.action,
        action.metadata.tokens_used,
        action.metadata.cost_usd
      );
    }
  }
}
