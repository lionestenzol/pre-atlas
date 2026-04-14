/**
 * Aegis Delta Fabric — Fastify JSON Schema Validators
 *
 * Reusable JSON Schema definitions for request/response validation.
 * Fastify validates automatically when schemas are attached to routes.
 */

export const tenantCreateSchema = {
  body: {
    type: 'object',
    required: ['name'],
    properties: {
      name: { type: 'string', minLength: 1, maxLength: 255 },
      tier: { type: 'string', enum: ['FREE', 'STARTER', 'ENTERPRISE'] },
      mode: { type: 'string', enum: ['RECOVER', 'CLOSURE', 'MAINTENANCE', 'BUILD', 'COMPOUND', 'SCALE'] },
      quotas: {
        type: 'object',
        properties: {
          max_agents: { type: 'integer', minimum: 1 },
          max_actions_per_hour: { type: 'integer', minimum: 1 },
          max_entities: { type: 'integer', minimum: 1 },
          max_delta_log_size: { type: 'integer', minimum: 1 },
          max_webhook_count: { type: 'integer', minimum: 0 },
        },
      },
    },
  },
} as const;

export const agentRegisterSchema = {
  body: {
    type: 'object',
    required: ['name', 'provider'],
    properties: {
      name: { type: 'string', minLength: 1, maxLength: 255 },
      provider: { type: 'string', enum: ['claude', 'openai', 'local', 'custom'] },
      version: { type: 'string', maxLength: 50 },
      capabilities: {
        type: 'array',
        items: {
          type: 'string',
          enum: [
            'create_task', 'update_task', 'complete_task', 'delete_task',
            'query_state', 'propose_delta', 'route_decision',
            'request_approval', 'get_policy_simulation', 'register_webhook',
          ],
        },
      },
      cost_center: { type: 'string', maxLength: 100 },
      metadata: { type: 'object' },
    },
  },
} as const;

export const agentActionSchema = {
  body: {
    type: 'object',
    required: ['agent_id'],
    properties: {
      agent_id: { type: 'string' },
      source: { type: 'string', enum: ['claude', 'openai', 'local', 'custom'] },
      // Claude format fields
      type: { type: 'string' },
      name: { type: 'string' },
      input: { type: 'object' },
      // OpenAI format fields
      function: { type: 'object' },
      // Direct format fields
      action: { type: 'string' },
      params: { type: 'object' },
      metadata: { type: 'object' },
      idempotency_key: { type: 'string' },
    },
  },
} as const;

export const deltaAppendSchema = {
  body: {
    type: 'object',
    required: ['author', 'patch'],
    properties: {
      tenant_id: { type: 'string' },
      author: {
        type: 'object',
        required: ['type', 'id'],
        properties: {
          type: { type: 'string', enum: ['agent', 'human', 'system', 'policy-engine'] },
          id: { type: 'string' },
          source: { type: 'string' },
        },
      },
      patch: {
        type: 'array',
        items: {
          type: 'object',
          required: ['op', 'path'],
          properties: {
            op: { type: 'string', enum: ['add', 'replace', 'remove'] },
            path: { type: 'string' },
            value: {},
          },
        },
      },
      entity_id: { type: 'string' },
      meta: {
        type: 'object',
        properties: {
          requestId: { type: 'string' },
          idempotencyKey: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    },
  },
} as const;

export const policyCreateSchema = {
  body: {
    type: 'object',
    properties: {
      rules: {
        type: 'array',
        items: {
          type: 'object',
          required: ['name', 'conditions', 'effect'],
          properties: {
            name: { type: 'string' },
            description: { type: 'string' },
            priority: { type: 'integer', minimum: 0 },
            conditions: {
              type: 'array',
              items: {
                type: 'object',
                required: ['field', 'operator', 'value'],
                properties: {
                  field: { type: 'string' },
                  operator: { type: 'string', enum: ['eq', 'neq', 'in', 'not_in', 'gt', 'lt', 'gte', 'lte', 'exists'] },
                  value: {},
                },
              },
            },
            effect: { type: 'string', enum: ['ALLOW', 'DENY', 'REQUIRE_HUMAN'] },
            reason: { type: 'string' },
          },
        },
      },
      rule: {
        type: 'object',
        required: ['name', 'conditions', 'effect'],
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          priority: { type: 'integer', minimum: 0 },
          conditions: { type: 'array' },
          effect: { type: 'string', enum: ['ALLOW', 'DENY', 'REQUIRE_HUMAN'] },
          reason: { type: 'string' },
        },
      },
    },
  },
} as const;

export const approvalDecideSchema = {
  body: {
    type: 'object',
    required: ['decision'],
    properties: {
      decision: { type: 'string', enum: ['APPROVED', 'REJECTED'] },
      decided_by: { type: 'string' },
      reason: { type: 'string' },
    },
  },
} as const;

export const stateQuerySchema = {
  querystring: {
    type: 'object',
    properties: {
      entity_id: { type: 'string' },
      entity_type: { type: 'string' },
      as_of_delta: { type: 'integer' },
      limit: { type: 'integer', minimum: 1, maximum: 1000 },
    },
  },
} as const;
