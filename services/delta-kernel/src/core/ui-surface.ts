/**
 * Delta-State Fabric v0 — Module 8: UI Surface Streaming
 *
 * Entities, schemas, and validators for ultra-low delta mirroring.
 * UI mirrors by component state, not pixels.
 */

import {
  UUID,
  Timestamp,
  Entity,
  Delta,
  JsonPatch,
  UIComponentKind,
  UIStateIndicator,
  UITextStyle,
  UISurfaceData,
  UIComponentStateData,
  UIRenderTickData,
  UISurfaceLinkData,
  UIComponentProps,
  UITextProps,
  UIGaugeProps,
  UIChartProps,
  UIListProps,
  UIIndicatorProps,
  UIButtonProps,
  UIListItem,
  RejectReason,
} from './types';
import { createEntity, applyDelta, now, generateUUID, computeHash } from './delta';

// === SCHEMA VALIDATORS ===

/**
 * Validate TEXT props
 */
function validateTextProps(props: unknown): props is UITextProps {
  const p = props as UITextProps;
  return (
    p.kind === 'TEXT' &&
    typeof p.text === 'string' &&
    ['PLAIN', 'BOLD', 'MUTED'].includes(p.style)
  );
}

/**
 * Validate GAUGE props
 */
function validateGaugeProps(props: unknown): props is UIGaugeProps {
  const p = props as UIGaugeProps;
  return (
    p.kind === 'GAUGE' &&
    typeof p.label === 'string' &&
    typeof p.value === 'number' &&
    typeof p.min === 'number' &&
    typeof p.max === 'number' &&
    typeof p.unit === 'string' &&
    ['OK', 'WARN', 'ALERT'].includes(p.state)
  );
}

/**
 * Validate CHART props
 */
function validateChartProps(props: unknown): props is UIChartProps {
  const p = props as UIChartProps;
  return (
    p.kind === 'CHART' &&
    typeof p.title === 'string' &&
    typeof p.series === 'object' &&
    typeof p.series.name === 'string' &&
    Array.isArray(p.series.points) &&
    p.series.points.every((pt: unknown) => typeof pt === 'number') &&
    typeof p.window === 'number'
  );
}

/**
 * Validate LIST props
 */
function validateListProps(props: unknown): props is UIListProps {
  const p = props as UIListProps;
  if (p.kind !== 'LIST' || typeof p.title !== 'string' || !Array.isArray(p.items)) {
    return false;
  }
  return p.items.every(
    (item: unknown) =>
      typeof (item as UIListItem).id === 'string' &&
      typeof (item as UIListItem).text === 'string' &&
      ['OK', 'WARN', 'ALERT'].includes((item as UIListItem).state)
  );
}

/**
 * Validate INDICATOR props
 */
function validateIndicatorProps(props: unknown): props is UIIndicatorProps {
  const p = props as UIIndicatorProps;
  return (
    p.kind === 'INDICATOR' &&
    typeof p.label === 'string' &&
    typeof p.on === 'boolean' &&
    ['OK', 'WARN', 'ALERT'].includes(p.state)
  );
}

/**
 * Validate BUTTON props
 */
function validateButtonProps(props: unknown): props is UIButtonProps {
  const p = props as UIButtonProps;
  return (
    p.kind === 'BUTTON' &&
    typeof p.label === 'string' &&
    typeof p.enabled === 'boolean' &&
    typeof p.action_id === 'string'
  );
}

/**
 * Validate component props based on kind
 */
export function validateComponentProps(kind: UIComponentKind, props: unknown): boolean {
  switch (kind) {
    case 'TEXT':
      return validateTextProps(props);
    case 'GAUGE':
      return validateGaugeProps(props);
    case 'CHART':
      return validateChartProps(props);
    case 'LIST':
      return validateListProps(props);
    case 'INDICATOR':
      return validateIndicatorProps(props);
    case 'BUTTON':
      return validateButtonProps(props);
    default:
      return false;
  }
}

// === DELTA VALIDATION (Streaming Contract) ===

/**
 * Allowed paths for each component kind
 */
const ALLOWED_PATHS: Record<UIComponentKind, Set<string>> = {
  TEXT: new Set(['/props/text', '/props/style']),
  GAUGE: new Set(['/props/value', '/props/state', '/props/label', '/props/min', '/props/max', '/props/unit']),
  CHART: new Set(['/props/series/points/-', '/props/title', '/props/window']),
  LIST: new Set(['/props/items/-', '/props/items', '/props/title']),
  INDICATOR: new Set(['/props/on', '/props/state', '/props/label']),
  BUTTON: new Set(['/props/enabled', '/props/label', '/props/action_id']),
};

/**
 * Validate a JSON patch operation against UI streaming contract
 */
export function validateUIPatch(
  kind: UIComponentKind,
  patch: JsonPatch
): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  // Check if path is allowed for this component kind
  const allowedPaths = ALLOWED_PATHS[kind];

  // Handle list item operations specially
  if (kind === 'LIST' && path.startsWith('/props/items/')) {
    // Allow add/replace/remove on items by index or by id
    if (op === 'add' && path === '/props/items/-') {
      // Append to list
      if (!isValidListItem(value)) {
        return { valid: false, reason: 'SCHEMA_INVALID' };
      }
      return { valid: true };
    }
    if (op === 'replace' && /^\/props\/items\/\d+$/.test(path)) {
      if (!isValidListItem(value)) {
        return { valid: false, reason: 'SCHEMA_INVALID' };
      }
      return { valid: true };
    }
    if (op === 'remove' && /^\/props\/items\/\d+$/.test(path)) {
      return { valid: true };
    }
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  // Handle chart point append
  if (kind === 'CHART' && path === '/props/series/points/-') {
    if (op !== 'add' || typeof value !== 'number') {
      return { valid: false, reason: 'SCHEMA_INVALID' };
    }
    return { valid: true };
  }

  // General scalar replace
  if (!allowedPaths.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  // Validate value type based on path
  if (path === '/props/state') {
    if (!['OK', 'WARN', 'ALERT'].includes(value as string)) {
      return { valid: false, reason: 'SCHEMA_INVALID' };
    }
  }

  if (path === '/props/style') {
    if (!['PLAIN', 'BOLD', 'MUTED'].includes(value as string)) {
      return { valid: false, reason: 'SCHEMA_INVALID' };
    }
  }

  if (path === '/props/on' || path === '/props/enabled') {
    if (typeof value !== 'boolean') {
      return { valid: false, reason: 'SCHEMA_INVALID' };
    }
  }

  if (path === '/props/value' || path === '/props/min' || path === '/props/max' || path === '/props/window') {
    if (typeof value !== 'number') {
      return { valid: false, reason: 'SCHEMA_INVALID' };
    }
  }

  return { valid: true };
}

function isValidListItem(value: unknown): value is UIListItem {
  const item = value as UIListItem;
  return (
    typeof item?.id === 'string' &&
    typeof item?.text === 'string' &&
    ['OK', 'WARN', 'ALERT'].includes(item?.state)
  );
}

// === SURFACE & COMPONENT CREATION ===

/**
 * Create a new UI Surface
 */
export async function createUISurface(
  name: string,
  rootComponentId: UUID
): Promise<{ entity: Entity; state: UISurfaceData; delta: Delta }> {
  const state: UISurfaceData = {
    name,
    schema_version: '0.1.0',
    root_component_id: rootComponentId,
    created_at: now(),
  };

  return createEntity('ui_surface', state);
}

/**
 * Create a new UI Component
 */
export async function createUIComponent(
  surfaceId: UUID,
  kind: UIComponentKind,
  props: UIComponentProps
): Promise<{ entity: Entity; state: UIComponentStateData; delta: Delta }> {
  if (!validateComponentProps(kind, props)) {
    throw new Error(`Invalid props for component kind: ${kind}`);
  }

  const state: UIComponentStateData = {
    surface_id: surfaceId,
    kind,
    props,
    created_at: now(),
  };

  return createEntity('ui_component', state);
}

/**
 * Create a UI Render Tick
 */
export async function createUIRenderTick(
  surfaceId: UUID,
  tick: number
): Promise<{ entity: Entity; state: UIRenderTickData; delta: Delta }> {
  const state: UIRenderTickData = {
    surface_id: surfaceId,
    tick,
    created_at: now(),
  };

  return createEntity('ui_render_tick', state);
}

/**
 * Create a UI Surface Link
 */
export async function createUISurfaceLink(
  surfaceId: UUID,
  senderNodeId: UUID,
  receiverNodeId: UUID
): Promise<{ entity: Entity; state: UISurfaceLinkData; delta: Delta }> {
  const state: UISurfaceLinkData = {
    surface_id: surfaceId,
    sender_node_id: senderNodeId,
    receiver_node_id: receiverNodeId,
    status: 'ACTIVE',
    created_at: now(),
  };

  return createEntity('ui_surface_link', state);
}

// === COMPONENT FACTORY HELPERS ===

/**
 * Create TEXT component props
 */
export function textProps(text: string, style: UITextStyle = 'PLAIN'): UITextProps {
  return { kind: 'TEXT', text, style };
}

/**
 * Create GAUGE component props
 */
export function gaugeProps(
  label: string,
  value: number,
  min: number,
  max: number,
  unit: string,
  state: UIStateIndicator = 'OK'
): UIGaugeProps {
  return { kind: 'GAUGE', label, value, min, max, unit, state };
}

/**
 * Create CHART component props
 */
export function chartProps(
  title: string,
  seriesName: string,
  points: number[] = [],
  window: number = 60
): UIChartProps {
  return {
    kind: 'CHART',
    title,
    series: { name: seriesName, points },
    window,
  };
}

/**
 * Create LIST component props
 */
export function listProps(title: string, items: UIListItem[] = []): UIListProps {
  return { kind: 'LIST', title, items };
}

/**
 * Create INDICATOR component props
 */
export function indicatorProps(
  label: string,
  on: boolean,
  state: UIStateIndicator = 'OK'
): UIIndicatorProps {
  return { kind: 'INDICATOR', label, on, state };
}

/**
 * Create BUTTON component props
 */
export function buttonProps(
  label: string,
  actionId: string,
  enabled: boolean = true
): UIButtonProps {
  return { kind: 'BUTTON', label, enabled, action_id: actionId };
}

// === COMPONENT REGISTRY ===

/**
 * Component registry for a surface
 */
export class ComponentRegistry {
  private components: Map<UUID, { entity: Entity; state: UIComponentStateData }> = new Map();
  private surfaceId: UUID;

  constructor(surfaceId: UUID) {
    this.surfaceId = surfaceId;
  }

  register(entity: Entity, state: UIComponentStateData): void {
    this.components.set(entity.entity_id, { entity, state });
  }

  get(componentId: UUID): { entity: Entity; state: UIComponentStateData } | undefined {
    return this.components.get(componentId);
  }

  getAll(): Array<{ entity: Entity; state: UIComponentStateData }> {
    return Array.from(this.components.values());
  }

  getByKind(kind: UIComponentKind): Array<{ entity: Entity; state: UIComponentStateData }> {
    return this.getAll().filter(c => c.state.kind === kind);
  }

  update(componentId: UUID, newState: UIComponentStateData): void {
    const existing = this.components.get(componentId);
    if (existing) {
      this.components.set(componentId, { entity: existing.entity, state: newState });
    }
  }

  size(): number {
    return this.components.size;
  }
}
