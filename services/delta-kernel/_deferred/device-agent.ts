/**
 * Delta-State Fabric v0 — Module 10: Device Agent
 *
 * Intent pickup, idempotent apply, and receipt publish.
 * Runs on the device node that owns actuators.
 */

import {
  UUID,
  Timestamp,
  Delta,
  JsonPatch,
  ActuatorData,
  ActuatorStateData,
  ActuatorStateValue,
  ActuationIntentData,
  ActuationReceiptData,
  ActuationOutcome,
  ControlMetrics,
} from './types';
import { now, generateUUID, computeHash, applyPatch } from './delta';
import { ControlSurfaceStore } from './control-surface';
import {
  IntentStore,
  ControlMetricsTracker,
  dispatchIntent,
  applyIntent,
  failIntent,
  createReceipt,
} from './actuation';

// === VIRTUAL ACTUATOR (for testing) ===

/**
 * Virtual actuator that simulates physical device behavior
 */
export class VirtualActuator {
  private actuatorId: UUID;
  private kind: string;
  private state: ActuatorStateValue = 'UNKNOWN';
  private value?: number | string;
  private failureRate: number = 0; // 0-1, chance of simulated failure

  constructor(actuatorId: UUID, kind: string, failureRate: number = 0) {
    this.actuatorId = actuatorId;
    this.kind = kind;
    this.failureRate = failureRate;
  }

  getActuatorId(): UUID {
    return this.actuatorId;
  }

  getState(): ActuatorStateValue {
    return this.state;
  }

  getValue(): number | string | undefined {
    return this.value;
  }

  /**
   * Simulate physical actuation
   */
  execute(action: 'SET_ON' | 'SET_OFF' | 'SET_VALUE', value?: number | string): {
    success: boolean;
    observedState: ActuatorStateValue;
    observedValue?: number | string;
    error?: string;
  } {
    // Simulate potential failure
    if (Math.random() < this.failureRate) {
      this.state = 'ERROR';
      return {
        success: false,
        observedState: 'ERROR',
        error: 'SIMULATED_HARDWARE_FAILURE',
      };
    }

    // Simulate state transition with brief "MOVING" state
    this.state = 'MOVING';

    // Execute the action
    switch (action) {
      case 'SET_ON':
        this.state = 'ON';
        if (this.kind === 'DIMMER') {
          this.value = 100;
        }
        break;

      case 'SET_OFF':
        this.state = 'OFF';
        if (this.kind === 'DIMMER') {
          this.value = 0;
        }
        break;

      case 'SET_VALUE':
        this.value = value;
        // For dimmers, map value to ON/OFF state
        if (this.kind === 'DIMMER' && typeof value === 'number') {
          this.state = value > 0 ? 'ON' : 'OFF';
        } else {
          this.state = 'ON';
        }
        break;
    }

    return {
      success: true,
      observedState: this.state,
      observedValue: this.value,
    };
  }

  /**
   * Reset actuator to initial state
   */
  reset(): void {
    this.state = 'UNKNOWN';
    this.value = undefined;
  }
}

// === DEVICE AGENT ===

/**
 * Device agent that manages actuators on a device node
 */
export class DeviceAgent {
  private nodeId: UUID;
  private virtualActuators: Map<UUID, VirtualActuator> = new Map();
  private actuatorStore: ControlSurfaceStore;
  private intentStore: IntentStore;
  private metrics: ControlMetricsTracker;
  private deltaLedger: Delta[] = [];

  constructor(
    nodeId: UUID,
    actuatorStore: ControlSurfaceStore,
    intentStore: IntentStore,
    metrics: ControlMetricsTracker
  ) {
    this.nodeId = nodeId;
    this.actuatorStore = actuatorStore;
    this.intentStore = intentStore;
    this.metrics = metrics;
  }

  /**
   * Register a virtual actuator for simulation
   */
  registerVirtualActuator(actuator: VirtualActuator): void {
    this.virtualActuators.set(actuator.getActuatorId(), actuator);
  }

  /**
   * Get all deltas produced by this agent
   */
  getDeltaLedger(): Delta[] {
    return [...this.deltaLedger];
  }

  /**
   * Clear the delta ledger
   */
  clearDeltaLedger(): void {
    this.deltaLedger = [];
  }

  /**
   * Poll for authorized intents and process them
   */
  processAuthorizedIntents(): ProcessingResult[] {
    const results: ProcessingResult[] = [];

    // Get all authorized intents for actuators owned by this node
    const authorizedIntents = this.intentStore.getAuthorizedIntentsForNode(
      this.nodeId,
      this.actuatorStore
    );

    for (const { id: intentId, state: intent, hash: intentHash } of authorizedIntents) {
      const result = this.processIntent(intentId, intent, intentHash);
      results.push(result);
    }

    return results;
  }

  /**
   * Process a single authorized intent
   */
  private processIntent(
    intentId: UUID,
    intent: ActuationIntentData,
    intentHash: string
  ): ProcessingResult {
    const actuatorId = intent.actuator_id;
    const currentTime = now();

    // 1. Check idempotency - has this intent already been applied?
    const actuatorState = this.actuatorStore.getActuatorStateByActuatorId(actuatorId);
    if (actuatorState && actuatorState.state.last_applied_intent_id === intentId) {
      this.metrics.recordDuplicatePrevented();
      return {
        intentId,
        status: 'SKIPPED',
        reason: 'ALREADY_APPLIED',
      };
    }

    // 2. Check if receipt already exists
    if (this.intentStore.hasReceiptForIntent(intentId)) {
      this.metrics.recordDuplicatePrevented();
      return {
        intentId,
        status: 'SKIPPED',
        reason: 'RECEIPT_EXISTS',
      };
    }

    // 3. Dispatch the intent
    const dispatchResult = dispatchIntent(intent);
    if (!dispatchResult.success) {
      return {
        intentId,
        status: 'FAILED',
        reason: 'DISPATCH_FAILED',
      };
    }

    // Update intent to DISPATCHED
    const dispatchedIntent = applyPatch(intent, dispatchResult.patches) as ActuationIntentData;
    this.intentStore.updateIntent(intentId, dispatchedIntent);
    this.emitIntentDelta(intentId, intentHash, dispatchResult.patches, dispatchedIntent);

    // 4. Execute on virtual actuator
    const virtualActuator = this.virtualActuators.get(actuatorId);
    let outcome: ActuationOutcome;
    let observedState: ActuatorStateValue;
    let observedValue: number | string | undefined;
    let errorReason: string | undefined;

    if (virtualActuator) {
      const execResult = virtualActuator.execute(
        intent.request.action,
        intent.request.value
      );
      outcome = execResult.success ? 'APPLIED' : 'FAILED';
      observedState = execResult.observedState;
      observedValue = execResult.observedValue;
      errorReason = execResult.error;
    } else {
      // No virtual actuator - simulate success
      outcome = 'APPLIED';
      observedState = intent.request.action === 'SET_OFF' ? 'OFF' : 'ON';
      observedValue = intent.request.value;
    }

    // 5. Update intent status
    const updatedIntentHash = computeHash(dispatchedIntent);
    let finalIntent: ActuationIntentData;
    let finalPatches: JsonPatch[];

    if (outcome === 'APPLIED') {
      const applyResult = applyIntent(dispatchedIntent);
      finalPatches = applyResult.patches;
      finalIntent = applyPatch(dispatchedIntent, finalPatches) as ActuationIntentData;
      this.metrics.recordIntentApplied(currentTime - intent.created_at);
    } else {
      const failResult = failIntent(dispatchedIntent, errorReason || 'EXECUTION_FAILED');
      finalPatches = failResult.patches;
      finalIntent = applyPatch(dispatchedIntent, finalPatches) as ActuationIntentData;
      this.metrics.recordIntentFailed();
    }

    this.intentStore.updateIntent(intentId, finalIntent);
    this.emitIntentDelta(intentId, updatedIntentHash, finalPatches, finalIntent);

    // 6. Update actuator state
    if (actuatorState) {
      const statePatches: JsonPatch[] = [
        { op: 'replace', path: '/state', value: observedState },
        { op: 'replace', path: '/updated_at', value: currentTime },
        { op: 'replace', path: '/last_applied_intent_id', value: intentId },
      ];

      if (observedValue !== undefined) {
        statePatches.push({ op: 'replace', path: '/value', value: observedValue });
      }

      const newActuatorState = applyPatch(actuatorState.state, statePatches) as ActuatorStateData;
      this.actuatorStore.updateActuatorState(actuatorState.id, newActuatorState);
      this.emitActuatorStateDelta(actuatorState.id, actuatorState.hash, statePatches, newActuatorState);
    }

    // 7. Create and register receipt
    const { receiptId, state: receiptState } = createReceipt(
      intentId,
      actuatorId,
      this.nodeId,
      outcome,
      observedState,
      observedValue
    );
    this.intentStore.registerReceipt(receiptId, receiptState);
    this.emitReceiptDelta(receiptId, receiptState);

    return {
      intentId,
      status: outcome === 'APPLIED' ? 'APPLIED' : 'FAILED',
      receiptId,
      observedState,
      observedValue,
      reason: errorReason,
    };
  }

  /**
   * Emit delta for intent state change
   */
  private emitIntentDelta(
    intentId: UUID,
    prevHash: string,
    patches: JsonPatch[],
    newState: ActuationIntentData
  ): void {
    const delta: Delta = {
      delta_id: generateUUID(),
      entity_id: intentId,
      timestamp: now(),
      author: 'system',
      patch: patches,
      prev_hash: prevHash,
      new_hash: computeHash(newState),
    };
    this.deltaLedger.push(delta);
  }

  /**
   * Emit delta for actuator state change
   */
  private emitActuatorStateDelta(
    stateId: UUID,
    prevHash: string,
    patches: JsonPatch[],
    newState: ActuatorStateData
  ): void {
    const delta: Delta = {
      delta_id: generateUUID(),
      entity_id: stateId,
      timestamp: now(),
      author: 'system',
      patch: patches,
      prev_hash: prevHash,
      new_hash: computeHash(newState),
    };
    this.deltaLedger.push(delta);
  }

  /**
   * Emit delta for new receipt
   */
  private emitReceiptDelta(receiptId: UUID, state: ActuationReceiptData): void {
    const patches: JsonPatch[] = Object.entries(state).map(([key, value]) => ({
      op: 'add' as const,
      path: `/${key}`,
      value,
    }));

    const delta: Delta = {
      delta_id: generateUUID(),
      entity_id: receiptId,
      timestamp: now(),
      author: 'system',
      patch: patches,
      prev_hash: '0'.repeat(64),
      new_hash: computeHash(state),
    };
    this.deltaLedger.push(delta);
  }

  /**
   * Check for expired intents and mark them
   */
  processExpiredIntents(): number {
    const currentTime = now();
    let expiredCount = 0;

    // Get all non-terminal intents
    const pendingStatuses: Array<'NEW' | 'AUTHORIZED' | 'DISPATCHED'> = ['NEW', 'AUTHORIZED', 'DISPATCHED'];

    for (const status of pendingStatuses) {
      const intents = this.intentStore.getIntentsByStatus(status);

      for (const { id: intentId, state: intent, hash: intentHash } of intents) {
        if (currentTime > intent.expires_at) {
          const patches: JsonPatch[] = [
            { op: 'replace', path: '/status', value: 'EXPIRED' },
            { op: 'replace', path: '/reason', value: 'TTL_EXCEEDED' },
          ];

          const expiredIntent = applyPatch(intent, patches) as ActuationIntentData;
          this.intentStore.updateIntent(intentId, expiredIntent);
          this.emitIntentDelta(intentId, intentHash, patches, expiredIntent);
          expiredCount++;
        }
      }
    }

    return expiredCount;
  }
}

// === PROCESSING RESULT ===

export interface ProcessingResult {
  intentId: UUID;
  status: 'APPLIED' | 'FAILED' | 'SKIPPED';
  receiptId?: UUID;
  observedState?: ActuatorStateValue;
  observedValue?: number | string;
  reason?: string;
}

// === REPLAY SAFETY ===

/**
 * Check if an intent can be safely replayed
 */
export function canReplayIntent(
  intent: ActuationIntentData,
  actuatorState: ActuatorStateData | undefined,
  intentStore: IntentStore,
  intentId: UUID
): { canReplay: boolean; reason?: string } {
  // Check if already applied via last_applied_intent_id
  if (actuatorState && actuatorState.last_applied_intent_id === intentId) {
    return { canReplay: false, reason: 'ALREADY_APPLIED_TO_STATE' };
  }

  // Check if receipt exists
  if (intentStore.hasReceiptForIntent(intentId)) {
    return { canReplay: false, reason: 'RECEIPT_EXISTS' };
  }

  // Intent is already in terminal state
  if (['APPLIED', 'FAILED', 'DENIED', 'EXPIRED'].includes(intent.status)) {
    return { canReplay: false, reason: 'TERMINAL_STATE' };
  }

  return { canReplay: true };
}

/**
 * Replay a ledger of deltas with idempotency checks
 */
export function replayDeltasWithIdempotency(
  deltas: Delta[],
  actuatorStore: ControlSurfaceStore,
  intentStore: IntentStore,
  agent: DeviceAgent
): { replayed: number; skipped: number; errors: number } {
  let replayed = 0;
  let skipped = 0;
  let errors = 0;

  // Sort by timestamp
  const sorted = [...deltas].sort((a, b) => a.timestamp - b.timestamp);

  for (const delta of sorted) {
    // Check if this is an intent we should process
    const intentData = intentStore.getIntent(delta.entity_id);
    if (intentData) {
      const actuatorState = actuatorStore.getActuatorStateByActuatorId(intentData.state.actuator_id);
      const check = canReplayIntent(
        intentData.state,
        actuatorState?.state,
        intentStore,
        delta.entity_id
      );

      if (!check.canReplay) {
        skipped++;
        continue;
      }
    }

    // Process the delta
    try {
      // Delta would be applied here - in real implementation
      replayed++;
    } catch {
      errors++;
    }
  }

  return { replayed, skipped, errors };
}
