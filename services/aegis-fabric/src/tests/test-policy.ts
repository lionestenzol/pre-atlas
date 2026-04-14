/**
 * Tests for the policy engine — condition evaluation, rule priority, simulation.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AegisStorage } from '../storage/aegis-storage.js';
import { PolicyStore } from '../policies/policy-store.js';
import { PolicyEngine } from '../policies/policy-engine.js';
import { DecisionCache } from '../policies/decision-cache.js';
import { PolicyEvaluationContext, PolicyRule } from '../core/types.js';
import { generateUUID, now } from '../core/delta.js';

export async function runPolicyTests() {
  const errors: string[] = [];
  let passed = 0;
  let failed = 0;

  const tmpDir = path.join(os.tmpdir(), `aegis-test-policy-${Date.now()}`);
  const storage = new AegisStorage({ dataDir: tmpDir });
  const policyStore = new PolicyStore(storage);
  const cache = new DecisionCache(1000);
  const engine = new PolicyEngine(policyStore, cache);
  const tenantId = 'test-tenant';

  const makeContext = (action: string, mode: string = 'BUILD'): PolicyEvaluationContext => ({
    tenant: { id: tenantId, tier: 'STARTER', mode: mode as any },
    agent: { id: 'agent-1', provider: 'claude', capabilities: ['create_task', 'delete_task', 'update_task', 'query_state'] },
    action: action as any,
    params: {},
    mode: mode as any,
  });

  // Test 1: Default ALLOW when no rules
  try {
    const decision = engine.evaluate(makeContext('create_task'));
    if (decision.effect !== 'ALLOW') throw new Error(`Expected ALLOW, got ${decision.effect}`);
    passed++;
  } catch (err) {
    errors.push(`Default allow: ${err}`);
    failed++;
  }

  // Test 2: DENY rule matches
  try {
    cache.clear();
    await policyStore.addRule(tenantId, {
      name: 'no-delete-in-closure',
      description: 'Block delete_task in CLOSURE mode',
      priority: 1,
      conditions: [
        { field: 'action', operator: 'eq', value: 'delete_task' },
        { field: 'mode', operator: 'eq', value: 'CLOSURE' },
      ],
      effect: 'DENY',
      reason: 'Cannot delete tasks during CLOSURE mode',
      enabled: true,
    });

    const decision = engine.evaluate(makeContext('delete_task', 'CLOSURE'));
    if (decision.effect !== 'DENY') throw new Error(`Expected DENY, got ${decision.effect}`);
    if (!decision.reason.includes('CLOSURE')) throw new Error('Reason should mention CLOSURE');
    passed++;
  } catch (err) {
    errors.push(`DENY rule: ${err}`);
    failed++;
  }

  // Test 3: Rule doesn't match different mode
  try {
    cache.clear();
    const decision = engine.evaluate(makeContext('delete_task', 'BUILD'));
    if (decision.effect !== 'ALLOW') throw new Error(`Expected ALLOW in BUILD, got ${decision.effect}`);
    passed++;
  } catch (err) {
    errors.push(`Mode mismatch: ${err}`);
    failed++;
  }

  // Test 4: REQUIRE_HUMAN effect
  try {
    cache.clear();
    await policyStore.addRule(tenantId, {
      name: 'require-human-for-enterprise',
      description: 'Enterprise tier actions need approval',
      priority: 10,
      conditions: [
        { field: 'tenant.tier', operator: 'eq', value: 'ENTERPRISE' },
      ],
      effect: 'REQUIRE_HUMAN',
      reason: 'Enterprise actions require human approval',
      enabled: true,
    });

    // Context with ENTERPRISE tier
    const ctx: PolicyEvaluationContext = {
      tenant: { id: tenantId, tier: 'ENTERPRISE', mode: 'BUILD' },
      agent: { id: 'agent-1', provider: 'claude', capabilities: ['create_task'] },
      action: 'create_task',
      params: {},
      mode: 'BUILD',
    };
    const decision = engine.evaluate(ctx);
    // The first rule (priority 1) is for delete_task in CLOSURE, not matching.
    // The ENTERPRISE rule (priority 10) should match.
    if (decision.effect !== 'REQUIRE_HUMAN') throw new Error(`Expected REQUIRE_HUMAN, got ${decision.effect}`);
    passed++;
  } catch (err) {
    errors.push(`REQUIRE_HUMAN: ${err}`);
    failed++;
  }

  // Test 5: Simulation mode
  try {
    cache.clear();
    const sim = engine.simulate(makeContext('delete_task', 'CLOSURE'));
    if (sim.decision.effect !== 'DENY') throw new Error('Simulation should DENY');
    if (sim.evaluated_rules.length === 0) throw new Error('Should show evaluated rules');
    passed++;
  } catch (err) {
    errors.push(`Simulation: ${err}`);
    failed++;
  }

  // Test 6: Decision caching
  try {
    cache.clear();
    const d1 = engine.evaluate(makeContext('create_task'));
    const d2 = engine.evaluate(makeContext('create_task'));
    if (d2.cached !== true) throw new Error('Second call should be cached');
    passed++;
  } catch (err) {
    errors.push(`Caching: ${err}`);
    failed++;
  }

  // Cleanup
  try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

  return { name: 'Policy Engine', passed, failed, errors };
}
