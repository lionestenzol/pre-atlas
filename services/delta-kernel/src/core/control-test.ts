/**
 * Delta-State Fabric v0 — Module 10: Control Test Harness
 *
 * Virtual Actuator tests proving:
 * 1. Intent → Authorized → Applied → Receipt flow
 * 2. Replay idempotency (no duplicate actuation)
 * 3. Out-of-bounds rejection
 * 4. TTL expiry rejection
 */

import {
  UUID,
  ActuatorData,
  ActuatorStateData,
  ActuationIntentData,
  Mode,
} from './types';
import { generateUUID, now, computeHash, applyPatch } from './delta';
import {
  ControlSurfaceStore,
  buttonWidget,
  sliderWidget,
} from './control-surface';
import {
  IntentStore,
  ControlMetricsTracker,
  createIntent,
  processNewIntent,
  PolicyContext,
  resetRateLimits,
} from './actuation';
import { DeviceAgent, VirtualActuator } from './device-agent';

// === TEST SETUP ===

interface TestHarness {
  nodeId: UUID;
  actuatorStore: ControlSurfaceStore;
  intentStore: IntentStore;
  metrics: ControlMetricsTracker;
  agent: DeviceAgent;
  relay1: { actuatorId: UUID; stateId: UUID };
  dimmer1: { actuatorId: UUID; stateId: UUID };
  systemMode: Mode;
}

function createTestHarness(): TestHarness {
  const nodeId = generateUUID();
  const actuatorStore = new ControlSurfaceStore();
  const intentStore = new IntentStore();
  const metrics = new ControlMetricsTracker();
  const agent = new DeviceAgent(nodeId, actuatorStore, intentStore, metrics);

  // Reset rate limits between tests
  resetRateLimits();

  // Create Relay1 (ON/OFF)
  const relay1ActuatorId = generateUUID();
  const relay1StateId = generateUUID();
  const createdAt = now();

  const relay1Actuator: ActuatorData = {
    name: 'Relay1',
    kind: 'RELAY',
    owner_node_id: nodeId,
    capabilities: {},
    created_at: createdAt,
  };

  const relay1State: ActuatorStateData = {
    actuator_id: relay1ActuatorId,
    owner_node_id: nodeId,
    state: 'OFF',
    updated_at: createdAt,
  };

  actuatorStore.registerActuator(relay1ActuatorId, relay1Actuator);
  actuatorStore.registerActuatorState(relay1StateId, relay1State);

  // Create virtual actuator
  const virtualRelay = new VirtualActuator(relay1ActuatorId, 'RELAY');
  agent.registerVirtualActuator(virtualRelay);

  // Create Dimmer1 (0-100)
  const dimmer1ActuatorId = generateUUID();
  const dimmer1StateId = generateUUID();

  const dimmer1Actuator: ActuatorData = {
    name: 'Dimmer1',
    kind: 'DIMMER',
    owner_node_id: nodeId,
    capabilities: {
      min: 0,
      max: 100,
      step: 1,
    },
    created_at: createdAt,
  };

  const dimmer1State: ActuatorStateData = {
    actuator_id: dimmer1ActuatorId,
    owner_node_id: nodeId,
    state: 'OFF',
    value: 0,
    updated_at: createdAt,
  };

  actuatorStore.registerActuator(dimmer1ActuatorId, dimmer1Actuator);
  actuatorStore.registerActuatorState(dimmer1StateId, dimmer1State);

  // Create virtual actuator
  const virtualDimmer = new VirtualActuator(dimmer1ActuatorId, 'DIMMER');
  agent.registerVirtualActuator(virtualDimmer);

  return {
    nodeId,
    actuatorStore,
    intentStore,
    metrics,
    agent,
    relay1: { actuatorId: relay1ActuatorId, stateId: relay1StateId },
    dimmer1: { actuatorId: dimmer1ActuatorId, stateId: dimmer1StateId },
    systemMode: 'BUILD',
  };
}

function createPolicyContext(harness: TestHarness, actuatorId: UUID): PolicyContext {
  const actuatorData = harness.actuatorStore.getActuator(actuatorId);
  const stateData = harness.actuatorStore.getActuatorStateByActuatorId(actuatorId);

  if (!actuatorData || !stateData) {
    throw new Error('Actuator not found');
  }

  return {
    systemMode: harness.systemMode,
    actuator: actuatorData.state,
    actuatorState: stateData.state,
    requestedByNodeId: harness.nodeId,
    currentTime: now(),
  };
}

// === TEST 1: Full Intent Flow ===

async function testFullIntentFlow(): Promise<boolean> {
  console.log('\n=== Test 1: Full Intent Flow ===\n');

  const harness = createTestHarness();

  // Create SET_ON intent for Relay1
  console.log('  Creating SET_ON intent for Relay1...');
  const { intentId, state: intentState } = createIntent(
    harness.relay1.actuatorId,
    harness.nodeId,
    'user',
    'SET_ON'
  );

  // Register intent
  harness.intentStore.registerIntent(intentId, intentState);

  // Process through authorization gate
  const context = createPolicyContext(harness, harness.relay1.actuatorId);
  const authResult = processNewIntent(
    intentId,
    intentState,
    context,
    harness.intentStore,
    harness.metrics
  );

  console.log(`  Authorization: ${authResult.authorized ? 'AUTHORIZED' : 'DENIED'}`);

  if (!authResult.authorized) {
    console.log(`  ✗ Intent was denied: ${authResult.reason}`);
    return false;
  }

  // Apply the authorization patches
  const authorizedIntent = applyPatch(intentState, authResult.patches) as ActuationIntentData;
  harness.intentStore.updateIntent(intentId, authorizedIntent);

  // Process authorized intents via device agent
  console.log('  Processing authorized intents...');
  const results = harness.agent.processAuthorizedIntents();

  if (results.length !== 1) {
    console.log(`  ✗ Expected 1 result, got ${results.length}`);
    return false;
  }

  const result = results[0];
  console.log(`  Intent ${result.intentId.slice(0, 8)}: ${result.status}`);
  console.log(`  Observed state: ${result.observedState}`);

  if (result.status !== 'APPLIED') {
    console.log(`  ✗ Intent was not applied: ${result.reason}`);
    return false;
  }

  // Verify receipt was created
  if (!result.receiptId) {
    console.log('  ✗ No receipt ID returned');
    return false;
  }

  const receipt = harness.intentStore.getReceipt(result.receiptId);
  if (!receipt) {
    console.log('  ✗ Receipt not found in store');
    return false;
  }

  console.log(`  Receipt created: ${receipt.state.outcome}`);

  // Verify actuator state was updated
  const finalState = harness.actuatorStore.getActuatorStateByActuatorId(harness.relay1.actuatorId);
  if (!finalState || finalState.state.state !== 'ON') {
    console.log(`  ✗ Actuator state not updated to ON`);
    return false;
  }

  console.log(`  Actuator state: ${finalState.state.state}`);
  console.log(`  Last applied intent: ${finalState.state.last_applied_intent_id?.slice(0, 8)}`);

  // Check metrics
  const metrics = harness.metrics.getMetrics();
  console.log(`\n  Metrics:`);
  console.log(`    Intents created: ${metrics.intents_created}`);
  console.log(`    Intents authorized: ${metrics.intents_authorized}`);
  console.log(`    Intents applied: ${metrics.intents_applied}`);

  if (metrics.intents_applied !== 1) {
    console.log('  ✗ Metrics show wrong number of applied intents');
    return false;
  }

  console.log('\n✓ Full intent flow successful');
  return true;
}

// === TEST 2: Replay Idempotency ===

async function testReplayIdempotency(): Promise<boolean> {
  console.log('\n=== Test 2: Replay Idempotency ===\n');

  const harness = createTestHarness();

  // Create and process first intent
  console.log('  Creating and applying first intent...');
  const { intentId, state: intentState } = createIntent(
    harness.relay1.actuatorId,
    harness.nodeId,
    'user',
    'SET_ON'
  );

  harness.intentStore.registerIntent(intentId, intentState);

  const context = createPolicyContext(harness, harness.relay1.actuatorId);
  const authResult = processNewIntent(
    intentId,
    intentState,
    context,
    harness.intentStore,
    harness.metrics
  );

  const authorizedIntent = applyPatch(intentState, authResult.patches) as ActuationIntentData;
  harness.intentStore.updateIntent(intentId, authorizedIntent);

  // First processing
  const results1 = harness.agent.processAuthorizedIntents();
  console.log(`  First processing: ${results1.length} intent(s) processed`);
  console.log(`  Result: ${results1[0]?.status}`);

  // Capture delta ledger for replay
  const originalDeltas = harness.agent.getDeltaLedger();
  console.log(`  Deltas emitted: ${originalDeltas.length}`);

  // "Replay" - try to process same intent again
  // Reset the intent status to AUTHORIZED to simulate replay
  const replayIntent: ActuationIntentData = {
    ...authorizedIntent,
    status: 'AUTHORIZED', // Force back to authorized
  };
  harness.intentStore.updateIntent(intentId, replayIntent);

  console.log('\n  Replaying same intent...');
  const results2 = harness.agent.processAuthorizedIntents();

  if (results2.length !== 1) {
    console.log(`  ✗ Expected 1 result, got ${results2.length}`);
    return false;
  }

  console.log(`  Replay result: ${results2[0].status}`);
  console.log(`  Reason: ${results2[0].reason}`);

  if (results2[0].status !== 'SKIPPED') {
    console.log('  ✗ Replay was not skipped!');
    return false;
  }

  // Check metrics
  const metrics = harness.metrics.getMetrics();
  console.log(`\n  Duplicates prevented: ${metrics.duplicates_prevented}`);

  if (metrics.duplicates_prevented !== 1) {
    console.log('  ✗ Duplicate prevention not recorded');
    return false;
  }

  if (metrics.intents_applied !== 1) {
    console.log('  ✗ Intent was applied more than once');
    return false;
  }

  console.log('\n✓ Replay idempotency verified');
  return true;
}

// === TEST 3: Out-of-Bounds Rejection ===

async function testOutOfBoundsRejection(): Promise<boolean> {
  console.log('\n=== Test 3: Out-of-Bounds Rejection ===\n');

  const harness = createTestHarness();

  // Try to set dimmer to 999 (max is 100)
  console.log('  Creating SET_VALUE=999 intent for Dimmer1 (max=100)...');
  const { intentId, state: intentState } = createIntent(
    harness.dimmer1.actuatorId,
    harness.nodeId,
    'user',
    'SET_VALUE',
    999  // Out of bounds!
  );

  harness.intentStore.registerIntent(intentId, intentState);

  const context = createPolicyContext(harness, harness.dimmer1.actuatorId);
  const authResult = processNewIntent(
    intentId,
    intentState,
    context,
    harness.intentStore,
    harness.metrics
  );

  console.log(`  Authorization: ${authResult.authorized ? 'AUTHORIZED' : 'DENIED'}`);
  console.log(`  Reason: ${authResult.reason}`);

  if (authResult.authorized) {
    console.log('  ✗ Out-of-bounds intent was incorrectly authorized!');
    return false;
  }

  if (authResult.reason !== 'VALUE_ABOVE_MAX') {
    console.log(`  ✗ Wrong rejection reason: ${authResult.reason}`);
    return false;
  }

  // Apply the denial patches
  const deniedIntent = applyPatch(intentState, authResult.patches) as ActuationIntentData;
  harness.intentStore.updateIntent(intentId, deniedIntent);

  // Verify intent is denied
  const finalIntent = harness.intentStore.getIntent(intentId);
  if (!finalIntent || finalIntent.state.status !== 'DENIED') {
    console.log('  ✗ Intent not marked as DENIED');
    return false;
  }

  console.log(`  Intent status: ${finalIntent.state.status}`);
  console.log(`  Intent reason: ${finalIntent.state.reason}`);

  // Check metrics
  const metrics = harness.metrics.getMetrics();
  console.log(`\n  Intents denied: ${metrics.intents_denied}`);

  if (metrics.intents_denied !== 1) {
    console.log('  ✗ Denial not recorded in metrics');
    return false;
  }

  // Test below min
  console.log('\n  Creating SET_VALUE=-10 intent for Dimmer1 (min=0)...');
  const { intentId: intentId2, state: intentState2 } = createIntent(
    harness.dimmer1.actuatorId,
    harness.nodeId,
    'user',
    'SET_VALUE',
    -10  // Below min!
  );

  harness.intentStore.registerIntent(intentId2, intentState2);

  const context2 = createPolicyContext(harness, harness.dimmer1.actuatorId);
  const authResult2 = processNewIntent(
    intentId2,
    intentState2,
    context2,
    harness.intentStore,
    harness.metrics
  );

  console.log(`  Authorization: ${authResult2.authorized ? 'AUTHORIZED' : 'DENIED'}`);
  console.log(`  Reason: ${authResult2.reason}`);

  if (authResult2.authorized) {
    console.log('  ✗ Below-min intent was incorrectly authorized!');
    return false;
  }

  console.log('\n✓ Out-of-bounds rejection verified');
  return true;
}

// === TEST 4: TTL Expiry Rejection ===

async function testTTLExpiry(): Promise<boolean> {
  console.log('\n=== Test 4: TTL Expiry Rejection ===\n');

  const harness = createTestHarness();

  // Create intent with very short TTL (already expired)
  console.log('  Creating intent with TTL=1ms (will be expired)...');
  const currentTime = now();

  const intentId = generateUUID();
  const intentState: ActuationIntentData = {
    actuator_id: harness.relay1.actuatorId,
    requested_by_node_id: harness.nodeId,
    requested_by_actor: 'user',
    request: {
      action: 'SET_ON',
    },
    policy: {
      requires_human_confirm: false,
      ttl_ms: 1,
    },
    status: 'NEW',
    created_at: currentTime - 1000, // Created 1 second ago
    expires_at: currentTime - 999,   // Expired 999ms ago
  };

  harness.intentStore.registerIntent(intentId, intentState);

  // Try to authorize - should fail due to expiry
  const context = createPolicyContext(harness, harness.relay1.actuatorId);
  const authResult = processNewIntent(
    intentId,
    intentState,
    context,
    harness.intentStore,
    harness.metrics
  );

  console.log(`  Authorization: ${authResult.authorized ? 'AUTHORIZED' : 'DENIED'}`);
  console.log(`  Reason: ${authResult.reason}`);

  if (authResult.authorized) {
    console.log('  ✗ Expired intent was incorrectly authorized!');
    return false;
  }

  if (authResult.reason !== 'INTENT_EXPIRED') {
    console.log(`  ✗ Wrong rejection reason: ${authResult.reason}`);
    return false;
  }

  // Apply the denial patches
  const deniedIntent = applyPatch(intentState, authResult.patches) as ActuationIntentData;
  harness.intentStore.updateIntent(intentId, deniedIntent);

  // Test the expire check on already-authorized intents
  console.log('\n  Testing expiry check on authorized intent...');
  const { intentId: intentId2, state: intentState2 } = createIntent(
    harness.relay1.actuatorId,
    harness.nodeId,
    'user',
    'SET_OFF',
    undefined,
    false,
    100 // 100ms TTL
  );

  harness.intentStore.registerIntent(intentId2, intentState2);

  const context2 = createPolicyContext(harness, harness.relay1.actuatorId);
  const authResult2 = processNewIntent(
    intentId2,
    intentState2,
    context2,
    harness.intentStore,
    harness.metrics
  );

  if (!authResult2.authorized) {
    console.log(`  ✗ Fresh intent was rejected: ${authResult2.reason}`);
    return false;
  }

  const authorizedIntent = applyPatch(intentState2, authResult2.patches) as ActuationIntentData;
  harness.intentStore.updateIntent(intentId2, authorizedIntent);

  // Wait for expiry
  console.log('  Waiting 150ms for expiry...');
  await new Promise(resolve => setTimeout(resolve, 150));

  // Run expiry check
  const expiredCount = harness.agent.processExpiredIntents();
  console.log(`  Expired intents: ${expiredCount}`);

  if (expiredCount !== 1) {
    console.log('  ✗ Expected 1 expired intent');
    return false;
  }

  // Verify intent is marked expired
  const expiredIntent = harness.intentStore.getIntent(intentId2);
  if (!expiredIntent || expiredIntent.state.status !== 'EXPIRED') {
    console.log(`  ✗ Intent not marked as EXPIRED: ${expiredIntent?.state.status}`);
    return false;
  }

  console.log(`  Intent status: ${expiredIntent.state.status}`);
  console.log(`  Intent reason: ${expiredIntent.state.reason}`);

  console.log('\n✓ TTL expiry rejection verified');
  return true;
}

// === RUN ALL TESTS ===

export async function runModule10Tests(): Promise<{ passed: number; failed: number }> {
  console.log('\n' + '='.repeat(60));
  console.log('MODULE 10: REMOTE CONTROL + ACTUATION DELTAS — PROOF TESTS');
  console.log('='.repeat(60));

  const tests = [
    { name: 'Full Intent Flow', fn: testFullIntentFlow },
    { name: 'Replay Idempotency', fn: testReplayIdempotency },
    { name: 'Out-of-Bounds Rejection', fn: testOutOfBoundsRejection },
    { name: 'TTL Expiry Rejection', fn: testTTLExpiry },
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      const result = await test.fn();
      if (result) {
        passed++;
      } else {
        failed++;
      }
    } catch (error) {
      console.log(`\n✗ Test "${test.name}" threw an error:`);
      console.log(`  ${error}`);
      failed++;
    }
  }

  console.log('\n' + '='.repeat(60));
  console.log(`RESULTS: ${passed} passed, ${failed} failed`);

  if (failed === 0) {
    console.log('✓ MODULE 10 COMPLETE — Bidirectional control plane proven!');
    console.log('  observe → decide → authorize → actuate → verify → record');
  }

  console.log('='.repeat(60) + '\n');

  return { passed, failed };
}

// Run if executed directly
if (typeof require !== 'undefined' && require.main === module) {
  runModule10Tests().catch(console.error);
}
