/**
 * Delta-State Fabric v0 — Module 10: Control Surface
 *
 * Schemas and validators for control surfaces and widgets.
 * Maps UI widgets to actuators for remote control.
 */

import {
  UUID,
  Timestamp,
  Delta,
  JsonPatch,
  ActuatorData,
  ActuatorKind,
  ActuatorStateData,
  ActuatorStateValue,
  ControlSurfaceData,
  ControlWidgetData,
  ControlWidgetKind,
  ActuationIntentData,
  ActuationIntentStatus,
  ActuationReceiptData,
  ActuationAction,
  RejectReason,
} from './types';
import { createEntity, now, generateUUID, computeHash } from './delta';

// === SCHEMA VALIDATORS ===

/**
 * Validate actuator kind
 */
function validateActuatorKind(kind: unknown): kind is ActuatorKind {
  return ['RELAY', 'SERVO', 'MOTOR', 'VALVE', 'DIMMER', 'SOFTWARE_TOGGLE', 'SOFTWARE_PARAM'].includes(kind as string);
}

/**
 * Validate actuator state value
 */
function validateActuatorStateValue(state: unknown): state is ActuatorStateValue {
  return ['UNKNOWN', 'OFF', 'ON', 'MOVING', 'ERROR'].includes(state as string);
}

/**
 * Validate widget kind
 */
function validateWidgetKind(kind: unknown): kind is ControlWidgetKind {
  return ['BUTTON', 'TOGGLE', 'SLIDER', 'SELECT'].includes(kind as string);
}

/**
 * Validate intent status
 */
function validateIntentStatus(status: unknown): status is ActuationIntentStatus {
  return ['NEW', 'AUTHORIZED', 'DENIED', 'EXPIRED', 'DISPATCHED', 'APPLIED', 'FAILED'].includes(status as string);
}

/**
 * Validate actuation action
 */
function validateActuationAction(action: unknown): action is ActuationAction {
  return ['SET_ON', 'SET_OFF', 'SET_VALUE'].includes(action as string);
}

// === DELTA VALIDATION (Streaming Contract) ===

/**
 * Allowed paths for ActuatorData
 */
const ACTUATOR_ALLOWED_PATHS = new Set([
  '/name',
  '/kind',
  '/capabilities/min',
  '/capabilities/max',
  '/capabilities/step',
  '/capabilities/allowed_values',
]);

/**
 * Allowed paths for ActuatorStateData
 */
const ACTUATOR_STATE_ALLOWED_PATHS = new Set([
  '/state',
  '/value',
  '/last_applied_intent_id',
  '/updated_at',
]);

/**
 * Allowed paths for ControlWidgetData
 */
const WIDGET_ALLOWED_PATHS = new Set([
  '/label',
  '/props/confirm',
  '/props/min',
  '/props/max',
  '/props/step',
  '/props/options',
]);

/**
 * Allowed paths for ActuationIntentData
 */
const INTENT_ALLOWED_PATHS = new Set([
  '/status',
  '/reason',
]);

/**
 * Validate actuator delta patch
 */
export function validateActuatorPatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!ACTUATOR_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/kind' && !validateActuatorKind(value)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/name' && typeof value !== 'string') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

/**
 * Validate actuator state delta patch
 */
export function validateActuatorStatePatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!ACTUATOR_STATE_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/state' && !validateActuatorStateValue(value)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/updated_at' && typeof value !== 'number') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

/**
 * Validate widget delta patch
 */
export function validateWidgetPatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!WIDGET_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/label' && typeof value !== 'string') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/props/confirm' && typeof value !== 'boolean') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

/**
 * Validate intent delta patch
 */
export function validateIntentPatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!INTENT_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/status' && !validateIntentStatus(value)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/reason' && typeof value !== 'string') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

// === ENTITY CREATION ===

/**
 * Create a new Actuator
 */
export async function createActuator(
  name: string,
  kind: ActuatorKind,
  ownerNodeId: UUID,
  capabilities: ActuatorData['capabilities'] = {}
): Promise<{ entity_id: UUID; state: ActuatorData; delta: Delta }> {
  const state: ActuatorData = {
    name,
    kind,
    owner_node_id: ownerNodeId,
    capabilities,
    created_at: now(),
  };

  const result = await createEntity('actuator', state);
  return { entity_id: result.entity.entity_id, state, delta: result.delta };
}

/**
 * Create initial Actuator State
 */
export async function createActuatorState(
  actuatorId: UUID,
  ownerNodeId: UUID,
  initialState: ActuatorStateValue = 'UNKNOWN',
  initialValue?: number | string
): Promise<{ entity_id: UUID; state: ActuatorStateData; delta: Delta }> {
  const state: ActuatorStateData = {
    actuator_id: actuatorId,
    owner_node_id: ownerNodeId,
    state: initialState,
    value: initialValue,
    updated_at: now(),
  };

  const result = await createEntity('actuator_state', state);
  return { entity_id: result.entity.entity_id, state, delta: result.delta };
}

/**
 * Create a Control Surface
 */
export async function createControlSurface(
  name: string
): Promise<{ entity_id: UUID; state: ControlSurfaceData; delta: Delta }> {
  const state: ControlSurfaceData = {
    name,
    schema_version: '0.1.0',
    created_at: now(),
  };

  const result = await createEntity('control_surface', state);
  return { entity_id: result.entity.entity_id, state, delta: result.delta };
}

/**
 * Create a Control Widget
 */
export async function createControlWidget(
  surfaceId: UUID,
  kind: ControlWidgetKind,
  label: string,
  targetActuatorId: UUID,
  props: ControlWidgetData['props']
): Promise<{ entity_id: UUID; state: ControlWidgetData; delta: Delta }> {
  const state: ControlWidgetData = {
    surface_id: surfaceId,
    kind,
    label,
    target_actuator_id: targetActuatorId,
    props,
    created_at: now(),
  };

  const result = await createEntity('control_widget', state);
  return { entity_id: result.entity.entity_id, state, delta: result.delta };
}

// === WIDGET FACTORIES ===

/**
 * Create a button widget for ON/OFF control
 */
export function buttonWidget(
  label: string,
  requireConfirm: boolean = false
): { kind: ControlWidgetKind; props: ControlWidgetData['props'] } {
  return {
    kind: 'BUTTON',
    props: { confirm: requireConfirm },
  };
}

/**
 * Create a toggle widget for ON/OFF state
 */
export function toggleWidget(
  requireConfirm: boolean = false
): { kind: ControlWidgetKind; props: ControlWidgetData['props'] } {
  return {
    kind: 'TOGGLE',
    props: { confirm: requireConfirm },
  };
}

/**
 * Create a slider widget for numeric values
 */
export function sliderWidget(
  min: number,
  max: number,
  step: number = 1,
  requireConfirm: boolean = false
): { kind: ControlWidgetKind; props: ControlWidgetData['props'] } {
  return {
    kind: 'SLIDER',
    props: { confirm: requireConfirm, min, max, step },
  };
}

/**
 * Create a select widget for enumerated values
 */
export function selectWidget(
  options: (number | string)[],
  requireConfirm: boolean = false
): { kind: ControlWidgetKind; props: ControlWidgetData['props'] } {
  return {
    kind: 'SELECT',
    props: { confirm: requireConfirm, options },
  };
}

// === CONTROL SURFACE STORE ===

/**
 * Store for control surface state
 */
export class ControlSurfaceStore {
  private actuators: Map<UUID, { state: ActuatorData; hash: string }> = new Map();
  private actuatorStates: Map<UUID, { state: ActuatorStateData; hash: string }> = new Map();
  private surfaces: Map<UUID, { state: ControlSurfaceData; hash: string }> = new Map();
  private widgets: Map<UUID, { state: ControlWidgetData; hash: string }> = new Map();
  private actuatorToState: Map<UUID, UUID> = new Map(); // actuator_id -> state entity_id

  registerActuator(id: UUID, state: ActuatorData): void {
    const hash = computeHash(state);
    this.actuators.set(id, { state, hash });
  }

  registerActuatorState(id: UUID, state: ActuatorStateData): void {
    const hash = computeHash(state);
    this.actuatorStates.set(id, { state, hash });
    this.actuatorToState.set(state.actuator_id, id);
  }

  registerSurface(id: UUID, state: ControlSurfaceData): void {
    const hash = computeHash(state);
    this.surfaces.set(id, { state, hash });
  }

  registerWidget(id: UUID, state: ControlWidgetData): void {
    const hash = computeHash(state);
    this.widgets.set(id, { state, hash });
  }

  getActuator(id: UUID): { state: ActuatorData; hash: string } | undefined {
    return this.actuators.get(id);
  }

  getActuatorState(id: UUID): { state: ActuatorStateData; hash: string } | undefined {
    return this.actuatorStates.get(id);
  }

  getActuatorStateByActuatorId(actuatorId: UUID): { id: UUID; state: ActuatorStateData; hash: string } | undefined {
    const stateId = this.actuatorToState.get(actuatorId);
    if (!stateId) return undefined;
    const data = this.actuatorStates.get(stateId);
    if (!data) return undefined;
    return { id: stateId, ...data };
  }

  getSurface(id: UUID): { state: ControlSurfaceData; hash: string } | undefined {
    return this.surfaces.get(id);
  }

  getWidget(id: UUID): { state: ControlWidgetData; hash: string } | undefined {
    return this.widgets.get(id);
  }

  updateActuatorState(id: UUID, newState: ActuatorStateData): void {
    const newHash = computeHash(newState);
    this.actuatorStates.set(id, { state: newState, hash: newHash });
  }

  getAllActuators(): Array<{ id: UUID; state: ActuatorData; hash: string }> {
    return Array.from(this.actuators.entries()).map(([id, data]) => ({ id, ...data }));
  }

  getAllActuatorStates(): Array<{ id: UUID; state: ActuatorStateData; hash: string }> {
    return Array.from(this.actuatorStates.entries()).map(([id, data]) => ({ id, ...data }));
  }

  getWidgetsForSurface(surfaceId: UUID): Array<{ id: UUID; state: ControlWidgetData; hash: string }> {
    return Array.from(this.widgets.entries())
      .filter(([_, data]) => data.state.surface_id === surfaceId)
      .map(([id, data]) => ({ id, ...data }));
  }

  getWidgetsForActuator(actuatorId: UUID): Array<{ id: UUID; state: ControlWidgetData; hash: string }> {
    return Array.from(this.widgets.entries())
      .filter(([_, data]) => data.state.target_actuator_id === actuatorId)
      .map(([id, data]) => ({ id, ...data }));
  }
}
