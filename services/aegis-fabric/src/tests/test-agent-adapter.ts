/**
 * Tests for the agent adapter — normalization of Claude, OpenAI, and custom formats.
 */

import { normalizeAgentAction } from '../agents/agent-adapter.js';

export async function runAdapterTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  const tenantId = 'tenant-1';
  const agentId = 'agent-1';
  const version = '1.0.0';

  // Test 1: Claude format
  try {
    const result = normalizeAgentAction(
      { type: 'tool_use', name: 'create_task', input: { title: 'From Claude', priority: 2 } },
      tenantId, agentId, version, 'claude'
    );
    if (!result.success) throw new Error(result.error);
    if (result.action!.action !== 'create_task') throw new Error('Wrong action');
    if (result.action!.params.title !== 'From Claude') throw new Error('Wrong params');
    if (result.action!.metadata.provider !== 'claude') throw new Error('Wrong provider');
    passed++;
  } catch (err) {
    errors.push(`Claude format: ${err}`);
    failed++;
  }

  // Test 2: OpenAI format
  try {
    const result = normalizeAgentAction(
      { function: { name: 'update_task', arguments: '{"task_id":"t1","title":"Updated"}' } },
      tenantId, agentId, version, 'openai'
    );
    if (!result.success) throw new Error(result.error);
    if (result.action!.action !== 'update_task') throw new Error('Wrong action');
    if (result.action!.params.task_id !== 't1') throw new Error('Wrong params');
    passed++;
  } catch (err) {
    errors.push(`OpenAI format: ${err}`);
    failed++;
  }

  // Test 3: Direct/custom format
  try {
    const result = normalizeAgentAction(
      { action: 'query_state', params: { entity_type: 'aegis_task' }, metadata: { model_id: 'local-v1' } },
      tenantId, agentId, version, 'local'
    );
    if (!result.success) throw new Error(result.error);
    if (result.action!.action !== 'query_state') throw new Error('Wrong action');
    if (result.action!.metadata.provider !== 'local') throw new Error('Wrong provider');
    passed++;
  } catch (err) {
    errors.push(`Direct format: ${err}`);
    failed++;
  }

  // Test 4: Invalid action name
  try {
    const result = normalizeAgentAction(
      { action: 'hack_system', params: {} },
      tenantId, agentId, version, 'custom'
    );
    if (result.success) throw new Error('Should have rejected invalid action');
    passed++;
  } catch (err) {
    errors.push(`Invalid action: ${err}`);
    failed++;
  }

  // Test 5: Unrecognized format
  try {
    const result = normalizeAgentAction(
      { foo: 'bar', baz: 123 },
      tenantId, agentId, version, 'custom'
    );
    if (result.success) throw new Error('Should have rejected unrecognized format');
    passed++;
  } catch (err) {
    errors.push(`Unrecognized format: ${err}`);
    failed++;
  }

  // Test 6: OpenAI with bad JSON arguments
  try {
    const result = normalizeAgentAction(
      { function: { name: 'create_task', arguments: 'not-json' } },
      tenantId, agentId, version, 'openai'
    );
    if (result.success) throw new Error('Should have rejected bad JSON');
    passed++;
  } catch (err) {
    errors.push(`Bad JSON: ${err}`);
    failed++;
  }

  return { name: 'Agent Adapter', passed, failed, errors };
}
