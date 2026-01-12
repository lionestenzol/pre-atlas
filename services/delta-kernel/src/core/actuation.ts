/**
 * Delta-State Fabric v0 — Module 10: Actuation Engine
 *
 * Intent creation, policy evaluation, and status transitions.
 * All control is state. No uncontrolled execution.
 */

import {
  UUID,
  Timestamp,
  Delta,
  JsonPatch,
  Author,
  Mode,
  SystemStateData,
  ActuatorData,
  ActuatorStateData,
  ActuatorStateValue,
  ActuationIntentData,
  ActuationIntentStatus,
  ActuationReceiptData,
  ActuationAction,
  ActuationOutcome,
  ControlMetrics,
  ControlWidgetData,
} from './types';
import { createEntity, now, generateUUID, computeHash, applyPatch } from './delta';
import { ControlSurfaceStore } from './control-surface';

// === METRICS TRACKER ===

export class ControlMetricsTracker {
  private metrics: ControlMetrics = {
    intents_created: 0,
    intents_authorized: 0,
    intents_denied: 0,
    intents_applied: 0,
    intents_failed: 0,
    median_time_to_apply_ms: 0,
    duplicates_prevented: 0,
  };

  private applyTimes: number[] = [];

  recordIntentCreated(): void {
    this.metrics.intents_created++;
  }

  recordIntentAuthorized(): void {
    this.metrics.intents_authorized++;
  }

  recordIntentDenied(): void {
    this.metrics.intents_denied++;
  }

  recordIntentApplied(timeToApplyMs: number): void {
    this.metrics.intents_applied++;
    this.applyTimes.push(timeToApplyMs);
    this.updateMedian();
  }

  recordIntentFailed(): void {
    this.metrics.intents_failed++;
  }

  recordDuplicatePrevented(): void {
    this.metrics.duplicates_prevented++;
  }

  private updateMedian(): void {
    if (this.applyTimes.length === 0) return;
    const sorted = [...this.applyTimes].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    this.metrics.median_time_to_apply_ms = sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  }

  getMetrics(): ControlMetrics {
    return { ...this.metrics };
  }

  reset(): void {
    this.metrics = {
      intents_created: 0,
      intents_authorized: 0,
      intents_denied: 0,
      intents_applied: 0,
      intents_failed: 0,
      median_time_to_apply_ms: 0,
      duplicates_prevented: 0,
    };
    this.applyTimes = [];
  }
}

// === INTENT STORE ===

export class IntentStore {
  private intents: Map<UUID, { state: ActuationIntentData; hash: string }> = new Map();
  private receipts: Map<UUID, { state: ActuationReceiptData; hash: string }> = new Map();
  private receiptsByIntent: Map<UUID, UUID> = new Map(); // intent_id -> receipt_id

  registerIntent(id: UUID, state: ActuationIntentData): void {
    const hash = computeHash(state);
    this.intents.set(id, { state, hash });
  }

  registerReceipt(id: UUID, state: ActuationReceiptData): void {
    const hash = computeHash(state);
    this.receipts.set(id, { state, hash });
    this.receiptsByIntent.set(state.intent_id, id);
  }

  getIntent(id: UUID): { state: ActuationIntentData; hash: string } | undefined {
    return this.intents.get(id);
  }

  getReceipt(id: UUID): { state: ActuationReceiptData; hash: string } | undefined {
    return this.receipts.get(id);
  }

  getReceiptByIntentId(intentId: UUID): { id: UUID; state: ActuationReceiptData; hash: string } | undefined {
    const receiptId = this.receiptsByIntent.get(intentId);
    if (!receiptId) return undefined;
    const data = this.receipts.get(receiptId);
    if (!data) return undefined;
    return { id: receiptId, ...data };
  }

  hasReceiptForIntent(intentId: UUID): boolean {
    return this.receiptsByIntent.has(intentId);
  }

  updateIntent(id: UUID, newState: ActuationIntentData): void {
    const newHash = computeHash(newState);
    this.intents.set(id, { state: newState, hash: newHash });
  }

  getIntentsByActuator(actuatorId: UUID): Array<{ id: UUID; state: ActuationIntentData; hash: string }> {
    return Array.from(this.intents.entries())
      .filter(([_, data]) => data.state.actuator_id === actuatorId)
      .map(([id, data]) => ({ id, ...data }));
  }

  getIntentsByStatus(status: ActuationIntentStatus): Array<{ id: UUID; state: ActuationIntentData; hash: string }> {
    return Array.from(this.intents.entries())
      .filter(([_, data]) => data.state.status === status)
      .map(([id, data]) => ({ id, ...data }));
  }

  getAuthorizedIntentsForNode(ownerNodeId: UUID, actuatorStore: ControlSurfaceStore): Array<{ id: UUID; state: ActuationIntentData; hash: string }> {
    return this.getIntentsByStatus('AUTHORIZED').filter(intent => {
      const actuator = actuatorStore.getActuator(intent.state.actuator_id);
      return actuator && actuator.state.owner_node_id === ownerNodeId;
    });
  }
}

// === POLICY ENGINE ===

export interface PolicyContext {
  systemMode: Mode;
  actuator: ActuatorData;
  actuatorState: ActuatorStateData;
  requestedByNodeId: UUID;
  currentTime: Timestamp;
}

export interface PolicyResult {
  authorized: boolean;
  reason?: string;
}

// Rate limit tracking
const rateLimitMap = new Map<UUID, { count: number; windowStart: Timestamp }>();
const RATE_LIMIT_WINDOW_MS = 10_000; // 10 seconds
const RATE_LIMIT_MAX = 3; // max 3 intents per window

/**
 * Deterministic policy engine - evaluates all policies
 */
export function evaluatePolicy(
  intent: ActuationIntentData,
  context: PolicyContext
): PolicyResult {
  // 1. TTL / Expiry check
  if (context.currentTime > intent.expires_at) {
    return { authorized: false, reason: 'INTENT_EXPIRED' };
  }

  // 2. Mode legality check
  const modeResult = checkModeLegality(intent, context.systemMode, context.actuator);
  if (!modeResult.authorized) {
    return modeResult;
  }

  // 3. Bounds check
  const boundsResult = checkBounds(intent, context.actuator);
  if (!boundsResult.authorized) {
    return boundsResult;
  }

  // 4. Rate limit check
  const rateResult = checkRateLimit(intent.actuator_id, context.currentTime);
  if (!rateResult.authorized) {
    return rateResult;
  }

  // 5. Ownership check (only owner node can apply, but any node can request)
  // This is checked at apply time, not at authorization

  return { authorized: true };
}

/**
 * Mode legality policy
 */
function checkModeLegality(
  intent: ActuationIntentData,
  mode: Mode,
  actuator: ActuatorData
): PolicyResult {
  // In RECOVER mode, deny high-risk actuations
  if (mode === 'RECOVER') {
    // Only allow software toggles and params in RECOVER
    if (!['SOFTWARE_TOGGLE', 'SOFTWARE_PARAM'].includes(actuator.kind)) {
      return { authorized: false, reason: 'MODE_RESTRICT_RECOVER' };
    }
  }

  return { authorized: true };
}

/**
 * Bounds check policy
 */
function checkBounds(
  intent: ActuationIntentData,
  actuator: ActuatorData
): PolicyResult {
  const { action, value } = intent.request;

  // SET_ON/SET_OFF don't need bounds check
  if (action !== 'SET_VALUE') {
    return { authorized: true };
  }

  if (value === undefined) {
    return { authorized: false, reason: 'VALUE_REQUIRED' };
  }

  const { capabilities } = actuator;

  // Check allowed_values if specified
  if (capabilities.allowed_values) {
    if (!capabilities.allowed_values.includes(value)) {
      return { authorized: false, reason: 'VALUE_NOT_ALLOWED' };
    }
  }

  // Check min/max for numeric values
  if (typeof value === 'number') {
    if (capabilities.min !== undefined && value < capabilities.min) {
      return { authorized: false, reason: 'VALUE_BELOW_MIN' };
    }
    if (capabilities.max !== undefined && value > capabilities.max) {
      return { authorized: false, reason: 'VALUE_ABOVE_MAX' };
    }
    if (capabilities.step !== undefined) {
      const stepsFromMin = (value - (capabilities.min || 0)) / capabilities.step;
      if (!Number.isInteger(stepsFromMin)) {
        return { authorized: false, reason: 'VALUE_NOT_ON_STEP' };
      }
    }
  }

  return { authorized: true };
}

/**
 * Rate limit policy
 */
function checkRateLimit(actuatorId: UUID, currentTime: Timestamp): PolicyResult {
  const entry = rateLimitMap.get(actuatorId);

  if (!entry) {
    rateLimitMap.set(actuatorId, { count: 1, windowStart: currentTime });
    return { authorized: true };
  }

  // Check if window has expired
  if (currentTime - entry.windowStart > RATE_LIMIT_WINDOW_MS) {
    rateLimitMap.set(actuatorId, { count: 1, windowStart: currentTime });
    return { authorized: true };
  }

  // Increment and check limit
  if (entry.count >= RATE_LIMIT_MAX) {
    return { authorized: false, reason: 'RATE_LIMITED' };
  }

  entry.count++;
  return { authorized: true };
}

/**
 * Reset rate limits (for testing)
 */
export function resetRateLimits(): void {
  rateLimitMap.clear();
}

// === INTENT CREATION ===

/**
 * Create a new actuation intent from widget interaction
 */
export function createIntent(
  actuatorId: UUID,
  requestedByNodeId: UUID,
  requestedByActor: Author,
  action: ActuationAction,
  value?: number | string,
  requiresConfirm: boolean = false,
  ttlMs: number = 30_000
): { intentId: UUID; state: ActuationIntentData } {
  const currentTime = now();
  const intentId = generateUUID();

  const state: ActuationIntentData = {
    actuator_id: actuatorId,
    requested_by_node_id: requestedByNodeId,
    requested_by_actor: requestedByActor,
    request: {
      action,
      value,
    },
    policy: {
      requires_human_confirm: requiresConfirm,
      ttl_ms: ttlMs,
    },
    status: 'NEW',
    created_at: currentTime,
    expires_at: currentTime + ttlMs,
  };

  return { intentId, state };
}

/**
 * Create intent from widget click
 */
export function createIntentFromWidget(
  widget: ControlWidgetData,
  requestedByNodeId: UUID,
  requestedByActor: Author,
  value?: number | string
): { intentId: UUID; state: ActuationIntentData } {
  let action: ActuationAction;

  switch (widget.kind) {
    case 'BUTTON':
      // Buttons typically toggle or turn on
      action = 'SET_ON';
      break;
    case 'TOGGLE':
      // Toggle will be determined by current state at apply time
      action = value ? 'SET_ON' : 'SET_OFF';
      break;
    case 'SLIDER':
    case 'SELECT':
      action = 'SET_VALUE';
      break;
    default:
      action = 'SET_ON';
  }

  return createIntent(
    widget.target_actuator_id,
    requestedByNodeId,
    requestedByActor,
    action,
    value,
    widget.props.confirm
  );
}

// === STATUS TRANSITIONS ===

/**
 * Transition intent to AUTHORIZED
 */
export function authorizeIntent(
  intent: ActuationIntentData,
  intentStore: IntentStore,
  intentId: UUID
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status !== 'NEW') {
    return { success: false, patches: [] };
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'AUTHORIZED' },
  ];

  return { success: true, patches };
}

/**
 * Transition intent to DENIED
 */
export function denyIntent(
  intent: ActuationIntentData,
  reason: string
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status !== 'NEW') {
    return { success: false, patches: [] };
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'DENIED' },
    { op: 'replace', path: '/reason', value: reason },
  ];

  return { success: true, patches };
}

/**
 * Transition intent to DISPATCHED
 */
export function dispatchIntent(
  intent: ActuationIntentData
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status !== 'AUTHORIZED') {
    return { success: false, patches: [] };
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'DISPATCHED' },
  ];

  return { success: true, patches };
}

/**
 * Transition intent to APPLIED
 */
export function applyIntent(
  intent: ActuationIntentData
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status !== 'DISPATCHED' && intent.status !== 'AUTHORIZED') {
    return { success: false, patches: [] };
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'APPLIED' },
  ];

  return { success: true, patches };
}

/**
 * Transition intent to FAILED
 */
export function failIntent(
  intent: ActuationIntentData,
  reason: string
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status !== 'DISPATCHED' && intent.status !== 'AUTHORIZED') {
    return { success: false, patches: [] };
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'FAILED' },
    { op: 'replace', path: '/reason', value: reason },
  ];

  return { success: true, patches };
}

/**
 * Transition intent to EXPIRED (called by TTL checker)
 */
export function expireIntent(
  intent: ActuationIntentData,
  currentTime: Timestamp
): { success: boolean; patches: JsonPatch[] } {
  if (intent.status === 'APPLIED' || intent.status === 'FAILED' || intent.status === 'DENIED') {
    return { success: false, patches: [] }; // Already terminal
  }

  if (currentTime <= intent.expires_at) {
    return { success: false, patches: [] }; // Not expired yet
  }

  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: 'EXPIRED' },
    { op: 'replace', path: '/reason', value: 'TTL_EXCEEDED' },
  ];

  return { success: true, patches };
}

// === RECEIPT CREATION ===

/**
 * Create actuation receipt after device applies intent
 */
export function createReceipt(
  intentId: UUID,
  actuatorId: UUID,
  ownerNodeId: UUID,
  outcome: ActuationOutcome,
  observedState: ActuatorStateValue,
  observedValue?: number | string
): { receiptId: UUID; state: ActuationReceiptData } {
  const receiptId = generateUUID();

  const state: ActuationReceiptData = {
    intent_id: intentId,
    actuator_id: actuatorId,
    owner_node_id: ownerNodeId,
    outcome,
    observed_state: {
      state: observedState,
      value: observedValue,
    },
    created_at: now(),
  };

  return { receiptId, state };
}

// === AUTHORIZATION FLOW ===

/**
 * Process a new intent through the authorization gate
 */
export function processNewIntent(
  intentId: UUID,
  intent: ActuationIntentData,
  context: PolicyContext,
  intentStore: IntentStore,
  metrics: ControlMetricsTracker
): { authorized: boolean; patches: JsonPatch[]; reason?: string } {
  metrics.recordIntentCreated();

  // Evaluate policy
  const policyResult = evaluatePolicy(intent, context);

  if (policyResult.authorized) {
    // Check if human confirmation is required
    if (intent.policy.requires_human_confirm) {
      // Intent stays NEW, waiting for PendingAction confirmation
      // The caller should create a PendingAction linked to this intent
      return { authorized: false, patches: [], reason: 'AWAITING_CONFIRMATION' };
    }

    // Authorize immediately
    const result = authorizeIntent(intent, intentStore, intentId);
    if (result.success) {
      metrics.recordIntentAuthorized();
      return { authorized: true, patches: result.patches };
    }
  }

  // Deny
  const denyResult = denyIntent(intent, policyResult.reason || 'POLICY_DENIED');
  metrics.recordIntentDenied();
  return { authorized: false, patches: denyResult.patches, reason: policyResult.reason };
}

/**
 * Confirm an intent that was awaiting human confirmation
 */
export function confirmIntent(
  intentId: UUID,
  intent: ActuationIntentData,
  context: PolicyContext,
  intentStore: IntentStore,
  metrics: ControlMetricsTracker
): { authorized: boolean; patches: JsonPatch[]; reason?: string } {
  if (intent.status !== 'NEW') {
    return { authorized: false, patches: [], reason: 'INVALID_STATUS' };
  }

  // Re-evaluate policy (bounds may have changed, TTL may have expired)
  const policyResult = evaluatePolicy(intent, context);

  if (policyResult.authorized) {
    const result = authorizeIntent(intent, intentStore, intentId);
    if (result.success) {
      metrics.recordIntentAuthorized();
      return { authorized: true, patches: result.patches };
    }
  }

  const denyResult = denyIntent(intent, policyResult.reason || 'POLICY_DENIED');
  metrics.recordIntentDenied();
  return { authorized: false, patches: denyResult.patches, reason: policyResult.reason };
}
