/**
 * Delta-State Fabric v0 — Module 8: UI Stream Operations
 *
 * Sender-side state capture and receiver-side rendering.
 * All UI updates go through controlled delta emission.
 */

import {
  UUID,
  Timestamp,
  Entity,
  Delta,
  JsonPatch,
  UIComponentKind,
  UIStateIndicator,
  UIComponentStateData,
  UIComponentProps,
  UIListItem,
  StreamMetrics,
  RejectReason,
} from './types';
import { applyDelta, now, computeHash, generateUUID, applyPatch } from './delta';
import { validateUIPatch, ComponentRegistry } from './ui-surface';

// === STREAM METRICS ===

/**
 * Metrics collector for proving ultra-low bandwidth
 */
export class MetricsCollector {
  private metrics: StreamMetrics = {
    deltas_sent: 0,
    bytes_sent: 0,
    avg_bytes_per_delta: 0,
    max_delta_bytes: 0,
    deltas_received: 0,
    bytes_received: 0,
    dropped_or_rejected: 0,
  };

  recordSent(deltaBytes: number): void {
    this.metrics.deltas_sent++;
    this.metrics.bytes_sent += deltaBytes;
    this.metrics.avg_bytes_per_delta = this.metrics.bytes_sent / this.metrics.deltas_sent;
    if (deltaBytes > this.metrics.max_delta_bytes) {
      this.metrics.max_delta_bytes = deltaBytes;
    }
  }

  recordReceived(deltaBytes: number): void {
    this.metrics.deltas_received++;
    this.metrics.bytes_received += deltaBytes;
  }

  recordDropped(): void {
    this.metrics.dropped_or_rejected++;
  }

  getMetrics(): StreamMetrics {
    return { ...this.metrics };
  }

  reset(): void {
    this.metrics = {
      deltas_sent: 0,
      bytes_sent: 0,
      avg_bytes_per_delta: 0,
      max_delta_bytes: 0,
      deltas_received: 0,
      bytes_received: 0,
      dropped_or_rejected: 0,
    };
  }

  /**
   * Get metrics formatted for display
   */
  getDisplayMetrics(elapsedMs: number): {
    bytesPerMin: number;
    deltasPerMin: number;
    avgBytesPerDelta: number;
  } {
    const minutes = elapsedMs / 60000;
    return {
      bytesPerMin: minutes > 0 ? this.metrics.bytes_sent / minutes : 0,
      deltasPerMin: minutes > 0 ? this.metrics.deltas_sent / minutes : 0,
      avgBytesPerDelta: this.metrics.avg_bytes_per_delta,
    };
  }
}

// === SENDER: STATE EXTRACTOR ===

/**
 * UI Stream Sender - extracts state changes and emits deltas
 */
export class UIStreamSender {
  private registry: ComponentRegistry;
  private metrics: MetricsCollector;
  private tickEnabled: boolean = false;
  private currentTick: number = 0;
  private pendingDeltas: Delta[] = [];

  constructor(registry: ComponentRegistry, metrics: MetricsCollector) {
    this.registry = registry;
    this.metrics = metrics;
  }

  enableTicks(): void {
    this.tickEnabled = true;
  }

  disableTicks(): void {
    this.tickEnabled = false;
  }

  /**
   * Set a scalar prop on a component (single value)
   */
  setProp(
    componentId: UUID,
    propPath: string,
    value: unknown
  ): Delta | null {
    const component = this.registry.get(componentId);
    if (!component) {
      console.error(`Component not found: ${componentId}`);
      return null;
    }

    const { entity, state } = component;
    const fullPath = `/props${propPath.startsWith('/') ? propPath : '/' + propPath}`;

    // Get current value
    const currentValue = this.getValueAtPath(state.props, propPath);
    if (currentValue === value) {
      // No change, emit nothing
      return null;
    }

    // Validate the patch
    const patch: JsonPatch = { op: 'replace', path: fullPath, value };
    const validation = validateUIPatch(state.kind, patch);
    if (!validation.valid) {
      console.error(`Invalid patch for ${state.kind}: ${validation.reason}`);
      this.metrics.recordDropped();
      return null;
    }

    // Create delta
    const delta = this.createComponentDelta(entity, state, [patch]);
    this.emitDelta(delta);
    return delta;
  }

  /**
   * Append a point to a chart series
   */
  appendPoint(componentId: UUID, value: number): Delta | null {
    const component = this.registry.get(componentId);
    if (!component) {
      console.error(`Component not found: ${componentId}`);
      return null;
    }

    const { entity, state } = component;
    if (state.kind !== 'CHART') {
      console.error(`appendPoint only valid for CHART components`);
      return null;
    }

    const patch: JsonPatch = {
      op: 'add',
      path: '/props/series/points/-',
      value,
    };

    const validation = validateUIPatch(state.kind, patch);
    if (!validation.valid) {
      this.metrics.recordDropped();
      return null;
    }

    const delta = this.createComponentDelta(entity, state, [patch]);
    this.emitDelta(delta);
    return delta;
  }

  /**
   * Add or update a list item (keyed by id)
   */
  upsertListItem(componentId: UUID, item: UIListItem): Delta | null {
    const component = this.registry.get(componentId);
    if (!component) {
      console.error(`Component not found: ${componentId}`);
      return null;
    }

    const { entity, state } = component;
    if (state.kind !== 'LIST') {
      console.error(`upsertListItem only valid for LIST components`);
      return null;
    }

    const listProps = state.props as { items: UIListItem[] };
    const existingIndex = listProps.items.findIndex(i => i.id === item.id);

    let patch: JsonPatch;
    if (existingIndex >= 0) {
      // Replace existing item
      patch = {
        op: 'replace',
        path: `/props/items/${existingIndex}`,
        value: item,
      };
    } else {
      // Add new item
      patch = {
        op: 'add',
        path: '/props/items/-',
        value: item,
      };
    }

    const validation = validateUIPatch(state.kind, patch);
    if (!validation.valid) {
      this.metrics.recordDropped();
      return null;
    }

    const delta = this.createComponentDelta(entity, state, [patch]);
    this.emitDelta(delta);
    return delta;
  }

  /**
   * Remove a list item by id
   */
  removeListItem(componentId: UUID, itemId: string): Delta | null {
    const component = this.registry.get(componentId);
    if (!component) {
      console.error(`Component not found: ${componentId}`);
      return null;
    }

    const { entity, state } = component;
    if (state.kind !== 'LIST') {
      console.error(`removeListItem only valid for LIST components`);
      return null;
    }

    const listProps = state.props as { items: UIListItem[] };
    const existingIndex = listProps.items.findIndex(i => i.id === itemId);

    if (existingIndex < 0) {
      return null; // Item doesn't exist
    }

    const patch: JsonPatch = {
      op: 'remove',
      path: `/props/items/${existingIndex}`,
    };

    const validation = validateUIPatch(state.kind, patch);
    if (!validation.valid) {
      this.metrics.recordDropped();
      return null;
    }

    const delta = this.createComponentDelta(entity, state, [patch]);
    this.emitDelta(delta);
    return delta;
  }

  /**
   * Get pending deltas and clear buffer
   */
  flush(): Delta[] {
    const deltas = this.pendingDeltas;
    this.pendingDeltas = [];
    if (this.tickEnabled) {
      this.currentTick++;
    }
    return deltas;
  }

  private getValueAtPath(obj: unknown, path: string): unknown {
    const parts = path.split('/').filter(p => p);
    let current: unknown = obj;
    for (const part of parts) {
      if (current && typeof current === 'object') {
        current = (current as Record<string, unknown>)[part];
      } else {
        return undefined;
      }
    }
    return current;
  }

  private createComponentDelta(
    entity: Entity,
    state: UIComponentStateData,
    patches: JsonPatch[]
  ): Delta {
    const delta: Delta = {
      delta_id: generateUUID(),
      entity_id: entity.entity_id,
      timestamp: now(),
      author: 'system',
      patch: patches,
      prev_hash: entity.current_hash,
      new_hash: '', // Will be computed
    };

    // Apply patch to get new state for hash computation
    const newState = applyDelta(state, delta);
    delta.new_hash = computeHash(newState);

    // Update registry with new state
    this.registry.update(entity.entity_id, newState as UIComponentStateData);

    return delta;
  }

  private emitDelta(delta: Delta): void {
    const deltaBytes = JSON.stringify(delta).length;
    this.metrics.recordSent(deltaBytes);
    this.pendingDeltas.push(delta);
  }
}

// === RECEIVER: STATE APPLIER ===

/**
 * UI Stream Receiver - applies deltas and maintains component state
 */
export class UIStreamReceiver {
  private registry: ComponentRegistry;
  private metrics: MetricsCollector;
  private entityStates: Map<UUID, { entity: Entity; state: UIComponentStateData }> = new Map();

  constructor(registry: ComponentRegistry, metrics: MetricsCollector) {
    this.registry = registry;
    this.metrics = metrics;
  }

  /**
   * Register initial component state
   */
  registerComponent(entity: Entity, state: UIComponentStateData): void {
    this.entityStates.set(entity.entity_id, { entity, state });
    this.registry.register(entity, state);
  }

  /**
   * Apply a delta from the sender
   */
  applyDelta(delta: Delta): { success: boolean; reason?: RejectReason } {
    const deltaBytes = JSON.stringify(delta).length;

    // Get current state
    const current = this.entityStates.get(delta.entity_id);
    if (!current) {
      this.metrics.recordDropped();
      return { success: false, reason: 'ENTITY_UNKNOWN' };
    }

    // Verify hash chain
    if (current.entity.current_hash !== delta.prev_hash) {
      this.metrics.recordDropped();
      return { success: false, reason: 'HASH_CHAIN_BROKEN' };
    }

    // Validate all patches
    for (const patch of delta.patch) {
      const validation = validateUIPatch(current.state.kind, patch);
      if (!validation.valid) {
        this.metrics.recordDropped();
        return { success: false, reason: validation.reason };
      }
    }

    // Apply delta
    const newState = applyDelta(current.state, delta) as UIComponentStateData;

    // Verify new hash
    const computedHash = computeHash(newState);
    if (computedHash !== delta.new_hash) {
      this.metrics.recordDropped();
      return { success: false, reason: 'HASH_CHAIN_BROKEN' };
    }

    // Update state
    const updatedEntity: Entity = {
      ...current.entity,
      current_version: current.entity.current_version + 1,
      current_hash: delta.new_hash,
    };

    this.entityStates.set(delta.entity_id, { entity: updatedEntity, state: newState });
    this.registry.update(delta.entity_id, newState);

    this.metrics.recordReceived(deltaBytes);
    return { success: true };
  }

  /**
   * Get current state for a component
   */
  getComponentState(componentId: UUID): UIComponentStateData | undefined {
    return this.entityStates.get(componentId)?.state;
  }

  /**
   * Get all component states for rendering
   */
  getAllStates(): Map<UUID, UIComponentStateData> {
    const result = new Map<UUID, UIComponentStateData>();
    for (const [id, { state }] of this.entityStates) {
      result.set(id, state);
    }
    return result;
  }

  /**
   * Replay deltas from ledger to reconstruct state
   */
  replay(deltas: Delta[]): { applied: number; rejected: number } {
    let applied = 0;
    let rejected = 0;

    // Sort deltas by timestamp
    const sorted = [...deltas].sort((a, b) => a.timestamp - b.timestamp);

    for (const delta of sorted) {
      const result = this.applyDelta(delta);
      if (result.success) {
        applied++;
      } else {
        rejected++;
      }
    }

    return { applied, rejected };
  }
}

// === DETERMINISTIC RENDERER ===

/**
 * Render a component to terminal output (for CLI)
 */
export function renderComponentToTerminal(state: UIComponentStateData): string[] {
  const { kind, props } = state;
  const lines: string[] = [];

  switch (kind) {
    case 'TEXT': {
      const p = props as { text: string; style: string };
      const style = p.style === 'BOLD' ? '\x1b[1m' : p.style === 'MUTED' ? '\x1b[2m' : '';
      lines.push(`${style}${p.text}\x1b[0m`);
      break;
    }

    case 'GAUGE': {
      const p = props as { label: string; value: number; min: number; max: number; unit: string; state: string };
      const pct = ((p.value - p.min) / (p.max - p.min)) * 100;
      const stateColor = p.state === 'OK' ? '\x1b[32m' : p.state === 'WARN' ? '\x1b[33m' : '\x1b[31m';
      const bar = '█'.repeat(Math.floor(pct / 5)) + '░'.repeat(20 - Math.floor(pct / 5));
      lines.push(`${p.label}: ${stateColor}${p.value}${p.unit}\x1b[0m`);
      lines.push(`[${bar}]`);
      break;
    }

    case 'CHART': {
      const p = props as { title: string; series: { name: string; points: number[] }; window: number };
      lines.push(`📈 ${p.title} (${p.series.name})`);
      const points = p.series.points.slice(-10); // Show last 10
      if (points.length > 0) {
        const min = Math.min(...points);
        const max = Math.max(...points);
        const range = max - min || 1;
        const sparkline = points.map(v => {
          const normalized = (v - min) / range;
          const chars = '▁▂▃▄▅▆▇█';
          return chars[Math.floor(normalized * 7)];
        }).join('');
        lines.push(sparkline);
      }
      break;
    }

    case 'LIST': {
      const p = props as { title: string; items: UIListItem[] };
      lines.push(`📋 ${p.title}`);
      for (const item of p.items.slice(0, 5)) {
        const stateIcon = item.state === 'OK' ? '✓' : item.state === 'WARN' ? '⚠' : '✗';
        const color = item.state === 'OK' ? '\x1b[32m' : item.state === 'WARN' ? '\x1b[33m' : '\x1b[31m';
        lines.push(`  ${color}${stateIcon}\x1b[0m ${item.text}`);
      }
      if (p.items.length > 5) {
        lines.push(`  ... and ${p.items.length - 5} more`);
      }
      break;
    }

    case 'INDICATOR': {
      const p = props as { label: string; on: boolean; state: string };
      const icon = p.on ? '●' : '○';
      const color = p.state === 'OK' ? '\x1b[32m' : p.state === 'WARN' ? '\x1b[33m' : '\x1b[31m';
      lines.push(`${color}${icon}\x1b[0m ${p.label}`);
      break;
    }

    case 'BUTTON': {
      const p = props as { label: string; enabled: boolean; action_id: string };
      const style = p.enabled ? '\x1b[44m\x1b[37m' : '\x1b[2m';
      lines.push(`${style}[ ${p.label} ]\x1b[0m`);
      break;
    }
  }

  return lines;
}

/**
 * Render entire surface to terminal
 */
export function renderSurfaceToTerminal(
  registry: ComponentRegistry
): string {
  const lines: string[] = [];
  const components = registry.getAll();

  for (const { state } of components) {
    lines.push(...renderComponentToTerminal(state));
    lines.push(''); // Spacing
  }

  return lines.join('\n');
}
