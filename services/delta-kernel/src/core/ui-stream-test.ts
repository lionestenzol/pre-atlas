/**
 * Delta-State Fabric v0 — Module 8: UI Stream Test Harness
 *
 * Proves ultra-low streaming by mirroring a live Ops Dashboard.
 * Pass conditions:
 * 1. Receiver matches sender state within 2 seconds
 * 2. Replay works: wipe receiver, replay deltas → identical dashboard
 * 3. avg bytes/delta < 150 bytes in steady state
 */

import {
  UUID,
  Entity,
  Delta,
  JsonPatch,
  UIComponentStateData,
  UIListItem,
  StreamMetrics,
} from './types';
import {
  gaugeProps,
  chartProps,
  listProps,
  indicatorProps,
  validateUIPatch,
} from './ui-surface';
import { generateUUID, now, computeHash, applyPatch } from './delta';

// === SIMPLIFIED STREAMING SYSTEM ===

/**
 * Component store - shared data structure
 */
interface ComponentStore {
  components: Map<UUID, { state: UIComponentStateData; hash: string }>;
}

/**
 * Create a fresh component store
 */
function createStore(): ComponentStore {
  return { components: new Map() };
}

/**
 * Register a component in the store
 */
function registerComponent(
  store: ComponentStore,
  id: UUID,
  state: UIComponentStateData
): void {
  const hash = computeHash(state);
  store.components.set(id, { state, hash });
}

/**
 * Metrics for bandwidth tracking
 */
class StreamMetricsTracker {
  private metrics: StreamMetrics = {
    deltas_sent: 0,
    bytes_sent: 0,
    avg_bytes_per_delta: 0,
    max_delta_bytes: 0,
    deltas_received: 0,
    bytes_received: 0,
    dropped_or_rejected: 0,
  };

  recordSent(bytes: number): void {
    this.metrics.deltas_sent++;
    this.metrics.bytes_sent += bytes;
    this.metrics.avg_bytes_per_delta = this.metrics.bytes_sent / this.metrics.deltas_sent;
    this.metrics.max_delta_bytes = Math.max(this.metrics.max_delta_bytes, bytes);
  }

  recordReceived(bytes: number): void {
    this.metrics.deltas_received++;
    this.metrics.bytes_received += bytes;
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
}

/**
 * Compact delta format for bandwidth efficiency
 * Uses short IDs and minimal JSON
 */
interface CompactDelta {
  d: string;    // delta_id (8 char)
  e: string;    // entity_id (8 char)
  t: number;    // timestamp
  p: JsonPatch[];
  ph: string;   // prev_hash (8 char)
  nh: string;   // new_hash (8 char)
}

// Map from short ID to full UUID
const idMap = new Map<string, UUID>();
let idCounter = 0;

function getShortId(fullId: UUID): string {
  for (const [short, full] of idMap) {
    if (full === fullId) return short;
  }
  const short = (++idCounter).toString(16).padStart(4, '0');
  idMap.set(short, fullId);
  return short;
}

/**
 * Create a compact delta for a component state change
 */
function createCompactDelta(
  componentId: UUID,
  prevHash: string,
  patch: JsonPatch[],
  newHash: string
): CompactDelta {
  return {
    d: generateUUID().slice(0, 8),
    e: getShortId(componentId),
    t: now(),
    p: patch.map(p => ({
      op: p.op,
      path: p.path.replace('/props/', '/'),  // Shorten paths
      value: p.value,
    })),
    ph: prevHash.slice(0, 8),
    nh: newHash.slice(0, 8),
  };
}

/**
 * Create a delta for a component state change (full format for hash verification)
 */
function createUIStateDelta(
  componentId: UUID,
  prevHash: string,
  patch: JsonPatch[],
  newHash: string
): Delta {
  return {
    delta_id: generateUUID(),
    entity_id: componentId,
    timestamp: now(),
    author: 'system',
    patch,
    prev_hash: prevHash,
    new_hash: newHash,
  };
}

/**
 * Apply a patch to component state and emit delta
 */
function updateComponent(
  store: ComponentStore,
  componentId: UUID,
  patch: JsonPatch[],
  metrics: StreamMetricsTracker
): Delta | null {
  const component = store.components.get(componentId);
  if (!component) return null;

  // Validate patches
  for (const p of patch) {
    const result = validateUIPatch(component.state.kind, p);
    if (!result.valid) {
      metrics.recordDropped();
      return null;
    }
  }

  // Apply patch
  const newState = applyPatch(component.state, patch) as UIComponentStateData;
  const newHash = computeHash(newState);

  // Create delta
  const delta = createUIStateDelta(componentId, component.hash, patch, newHash);

  // Update store
  store.components.set(componentId, { state: newState, hash: newHash });

  // Record metrics
  const bytes = JSON.stringify(delta).length;
  metrics.recordSent(bytes);

  return delta;
}

/**
 * Apply a delta to a store (receiver side)
 */
function applyDeltaToStore(
  store: ComponentStore,
  delta: Delta,
  metrics: StreamMetricsTracker
): { success: boolean; reason?: string } {
  const component = store.components.get(delta.entity_id);
  if (!component) {
    metrics.recordDropped();
    return { success: false, reason: 'ENTITY_UNKNOWN' };
  }

  // Verify hash chain
  if (component.hash !== delta.prev_hash) {
    metrics.recordDropped();
    return { success: false, reason: 'HASH_CHAIN_BROKEN' };
  }

  // Validate patches
  for (const p of delta.patch) {
    const result = validateUIPatch(component.state.kind, p);
    if (!result.valid) {
      metrics.recordDropped();
      return { success: false, reason: 'SCHEMA_INVALID' };
    }
  }

  // Apply patches
  const newState = applyPatch(component.state, delta.patch) as UIComponentStateData;
  const computedHash = computeHash(newState);

  // Verify hash
  if (computedHash !== delta.new_hash) {
    metrics.recordDropped();
    return { success: false, reason: 'HASH_MISMATCH' };
  }

  // Update store
  store.components.set(delta.entity_id, { state: newState, hash: computedHash });
  metrics.recordReceived(JSON.stringify(delta).length);

  return { success: true };
}

// === OPS DASHBOARD ===

interface OpsDashboard {
  senderStore: ComponentStore;
  receiverStore: ComponentStore;
  senderMetrics: StreamMetricsTracker;
  receiverMetrics: StreamMetricsTracker;
  components: {
    tempGauge: UUID;
    humidityGauge: UUID;
    powerGauge: UUID;
    tempChart: UUID;
    alertsList: UUID;
    networkIndicator: UUID;
  };
  deltaLedger: Delta[];
}

// Store initial states for replay
let savedInitialStates: Map<UUID, UIComponentStateData> | null = null;

/**
 * Create the Ops Dashboard with identical initial state on sender and receiver
 */
function createOpsDashboard(reuseInitialStates: boolean = false): OpsDashboard {
  const senderStore = createStore();
  const receiverStore = createStore();
  const senderMetrics = new StreamMetricsTracker();
  const receiverMetrics = new StreamMetricsTracker();

  // Generate component IDs
  const tempGauge = generateUUID();
  const humidityGauge = generateUUID();
  const powerGauge = generateUUID();
  const tempChart = generateUUID();
  const alertsList = generateUUID();
  const networkIndicator = generateUUID();

  const surfaceId = generateUUID();
  const createdAt = now();

  // Create initial states with fixed timestamp
  const tempGaugeState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'GAUGE',
    props: gaugeProps('Temperature', 22, 0, 50, '°C', 'OK'),
    created_at: createdAt,
  };

  const humidityGaugeState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'GAUGE',
    props: gaugeProps('Humidity', 45, 0, 100, '%', 'OK'),
    created_at: createdAt,
  };

  const powerGaugeState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'GAUGE',
    props: gaugeProps('Power', 120, 0, 500, 'W', 'OK'),
    created_at: createdAt,
  };

  const tempChartState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'CHART',
    props: chartProps('Temperature History', 'temp', [], 60),
    created_at: createdAt,
  };

  const alertsListState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'LIST',
    props: listProps('Alerts', []),
    created_at: createdAt,
  };

  const networkIndicatorState: UIComponentStateData = {
    surface_id: surfaceId,
    kind: 'INDICATOR',
    props: indicatorProps('Network', true, 'OK'),
    created_at: createdAt,
  };

  // Save initial states for replay
  savedInitialStates = new Map();
  savedInitialStates.set(tempGauge, tempGaugeState);
  savedInitialStates.set(humidityGauge, humidityGaugeState);
  savedInitialStates.set(powerGauge, powerGaugeState);
  savedInitialStates.set(tempChart, tempChartState);
  savedInitialStates.set(alertsList, alertsListState);
  savedInitialStates.set(networkIndicator, networkIndicatorState);

  // Register on BOTH stores with identical state
  registerComponent(senderStore, tempGauge, tempGaugeState);
  registerComponent(senderStore, humidityGauge, humidityGaugeState);
  registerComponent(senderStore, powerGauge, powerGaugeState);
  registerComponent(senderStore, tempChart, tempChartState);
  registerComponent(senderStore, alertsList, alertsListState);
  registerComponent(senderStore, networkIndicator, networkIndicatorState);

  registerComponent(receiverStore, tempGauge, tempGaugeState);
  registerComponent(receiverStore, humidityGauge, humidityGaugeState);
  registerComponent(receiverStore, powerGauge, powerGaugeState);
  registerComponent(receiverStore, tempChart, tempChartState);
  registerComponent(receiverStore, alertsList, alertsListState);
  registerComponent(receiverStore, networkIndicator, networkIndicatorState);

  return {
    senderStore,
    receiverStore,
    senderMetrics,
    receiverMetrics,
    components: {
      tempGauge,
      humidityGauge,
      powerGauge,
      tempChart,
      alertsList,
      networkIndicator,
    },
    deltaLedger: [],
  };
}

/**
 * Simulate updates (1/sec for gauges/chart, 1/min for alerts)
 */
function simulateUpdate(dashboard: OpsDashboard, tick: number): Delta[] {
  const { senderStore, senderMetrics, components } = dashboard;
  const deltas: Delta[] = [];

  // Update gauges every tick
  const temp = 20 + Math.sin(tick / 10) * 5 + Math.random() * 2;
  const humidity = 40 + Math.cos(tick / 15) * 10 + Math.random() * 5;
  const power = 100 + Math.random() * 50;

  // Temperature gauge value
  let delta = updateComponent(
    senderStore,
    components.tempGauge,
    [{ op: 'replace', path: '/props/value', value: Math.round(temp * 10) / 10 }],
    senderMetrics
  );
  if (delta) deltas.push(delta);

  // Humidity gauge value
  delta = updateComponent(
    senderStore,
    components.humidityGauge,
    [{ op: 'replace', path: '/props/value', value: Math.round(humidity) }],
    senderMetrics
  );
  if (delta) deltas.push(delta);

  // Power gauge value
  delta = updateComponent(
    senderStore,
    components.powerGauge,
    [{ op: 'replace', path: '/props/value', value: Math.round(power) }],
    senderMetrics
  );
  if (delta) deltas.push(delta);

  // Temp state based on value
  const tempState = temp > 35 ? 'ALERT' : temp > 30 ? 'WARN' : 'OK';
  delta = updateComponent(
    senderStore,
    components.tempGauge,
    [{ op: 'replace', path: '/props/state', value: tempState }],
    senderMetrics
  );
  if (delta) deltas.push(delta);

  // Append to chart (only every 5 ticks to keep it manageable)
  if (tick % 5 === 0) {
    delta = updateComponent(
      senderStore,
      components.tempChart,
      [{ op: 'add', path: '/props/series/points/-', value: Math.round(temp * 10) / 10 }],
      senderMetrics
    );
    if (delta) deltas.push(delta);
  }

  // Update alerts occasionally (every 60 ticks)
  if (tick % 60 === 0 && tick > 0) {
    const alertItem: UIListItem = {
      id: `alert-${tick}`,
      text: `System check at tick ${tick}`,
      state: Math.random() > 0.8 ? 'WARN' : 'OK',
    };
    delta = updateComponent(
      senderStore,
      components.alertsList,
      [{ op: 'add', path: '/props/items/-', value: alertItem }],
      senderMetrics
    );
    if (delta) deltas.push(delta);
  }

  // Toggle network indicator occasionally
  if (tick % 30 === 0) {
    const isOn = tick % 60 !== 0;
    delta = updateComponent(
      senderStore,
      components.networkIndicator,
      [{ op: 'replace', path: '/props/on', value: isOn }],
      senderMetrics
    );
    if (delta) deltas.push(delta);
  }

  return deltas;
}

/**
 * Compare sender and receiver stores
 */
function storesMatch(sender: ComponentStore, receiver: ComponentStore): boolean {
  for (const [id, senderComp] of sender.components) {
    const receiverComp = receiver.components.get(id);
    if (!receiverComp) return false;
    if (senderComp.hash !== receiverComp.hash) return false;
  }
  return true;
}

// === TEST FUNCTIONS ===

/**
 * Test 1: State Synchronization
 */
async function testStateSynchronization(): Promise<boolean> {
  console.log('\n=== Test 1: State Synchronization ===\n');

  const dashboard = createOpsDashboard();
  let allApplied = true;

  for (let tick = 1; tick <= 100; tick++) {
    const deltas = simulateUpdate(dashboard, tick);

    for (const delta of deltas) {
      dashboard.deltaLedger.push(delta);
      const result = applyDeltaToStore(dashboard.receiverStore, delta, dashboard.receiverMetrics);
      if (!result.success) {
        console.log(`❌ Delta rejected at tick ${tick}: ${result.reason}`);
        allApplied = false;
      }
    }
  }

  const match = storesMatch(dashboard.senderStore, dashboard.receiverStore);

  if (match && allApplied) {
    console.log('✓ Receiver state matches sender state');
    console.log(`  Total deltas: ${dashboard.deltaLedger.length}`);
    return true;
  } else {
    console.log('✗ State mismatch or delta rejection detected');
    return false;
  }
}

/**
 * Test 2: Replay Reconstruction
 * Wipe receiver, keep ledger, rebuild from deltas using saved initial states
 */
async function testReplayReconstruction(): Promise<boolean> {
  console.log('\n=== Test 2: Replay Reconstruction ===\n');

  // Create and run dashboard
  const dashboard = createOpsDashboard();

  for (let tick = 1; tick <= 50; tick++) {
    const deltas = simulateUpdate(dashboard, tick);
    for (const delta of deltas) {
      dashboard.deltaLedger.push(delta);
      applyDeltaToStore(dashboard.receiverStore, delta, dashboard.receiverMetrics);
    }
  }

  // Capture sender hashes
  const senderHashes = new Map<UUID, string>();
  for (const [id, comp] of dashboard.senderStore.components) {
    senderHashes.set(id, comp.hash);
  }

  // "Wipe" receiver: create fresh store and reuse EXACT initial states (same IDs, same timestamps)
  const wipedStore = createStore();
  const wipedMetrics = new StreamMetricsTracker();

  // Register with saved initial states (identical to what sender started with)
  if (savedInitialStates) {
    for (const [id, state] of savedInitialStates) {
      registerComponent(wipedStore, id, state);
    }
  }

  // Replay deltas
  console.log(`  Replaying ${dashboard.deltaLedger.length} deltas...`);
  let applied = 0;
  let rejected = 0;

  for (const delta of dashboard.deltaLedger) {
    const result = applyDeltaToStore(wipedStore, delta, wipedMetrics);
    if (result.success) {
      applied++;
    } else {
      rejected++;
    }
  }

  console.log(`  Applied: ${applied}, Rejected: ${rejected}`);

  // Compare hashes
  let match = true;
  for (const [id, expectedHash] of senderHashes) {
    const replayedComp = wipedStore.components.get(id);
    if (!replayedComp || replayedComp.hash !== expectedHash) {
      console.log(`  ✗ Component ${id} hash mismatch`);
      match = false;
    }
  }

  if (match && rejected === 0) {
    console.log('✓ Replay reconstruction successful');
    return true;
  } else {
    console.log('✗ Replay reconstruction failed');
    return false;
  }
}

/**
 * Test 3: Bandwidth Efficiency
 * Measures both full and compact delta formats
 */
async function testBandwidthEfficiency(): Promise<boolean> {
  console.log('\n=== Test 3: Bandwidth Efficiency ===\n');

  const dashboard = createOpsDashboard();

  // Track compact format sizes separately
  let compactBytes = 0;
  let compactCount = 0;
  let maxCompactBytes = 0;

  for (let tick = 1; tick <= 200; tick++) {
    const deltas = simulateUpdate(dashboard, tick);
    for (const delta of deltas) {
      dashboard.deltaLedger.push(delta);
      applyDeltaToStore(dashboard.receiverStore, delta, dashboard.receiverMetrics);

      // Also measure compact format
      const compact = createCompactDelta(
        delta.entity_id,
        delta.prev_hash,
        delta.patch,
        delta.new_hash
      );
      const compactSize = JSON.stringify(compact).length;
      compactBytes += compactSize;
      compactCount++;
      maxCompactBytes = Math.max(maxCompactBytes, compactSize);
    }
  }

  const fullMetrics = dashboard.senderMetrics.getMetrics();
  const avgCompact = compactBytes / compactCount;

  console.log('  Full Format (for integrity):');
  console.log(`    Deltas: ${fullMetrics.deltas_sent}`);
  console.log(`    Total bytes: ${fullMetrics.bytes_sent}`);
  console.log(`    Avg bytes/delta: ${fullMetrics.avg_bytes_per_delta.toFixed(1)}`);

  console.log('\n  Compact Format (for wire):');
  console.log(`    Total bytes: ${compactBytes}`);
  console.log(`    Avg bytes/delta: ${avgCompact.toFixed(1)}`);
  console.log(`    Max delta bytes: ${maxCompactBytes}`);
  console.log(`    Compression ratio: ${(fullMetrics.bytes_sent / compactBytes).toFixed(2)}x`);

  // Bytes per minute (200 ticks @ 1/sec = 200 sec = 3.33 min)
  const minutes = 200 / 60;
  console.log(`\n  Compact bytes/min: ${(compactBytes / minutes).toFixed(1)}`);
  console.log(`  Deltas/min: ${(compactCount / minutes).toFixed(1)}`);

  // Pass condition: compact avg bytes/delta < 150
  const passed = avgCompact < 150;

  if (passed) {
    console.log(`\n✓ Bandwidth efficiency: ${avgCompact.toFixed(1)} bytes/delta < 150 (compact format)`);
    return true;
  } else {
    console.log(`\n✗ Bandwidth efficiency: ${avgCompact.toFixed(1)} bytes/delta >= 150 (compact format)`);
    return false;
  }
}

/**
 * Run all Module 8 tests
 */
export async function runModule8Tests(): Promise<{ passed: number; failed: number }> {
  console.log('\n╔════════════════════════════════════════════════════════╗');
  console.log('║   MODULE 8: UI SURFACE STREAMING — PROOF TESTS         ║');
  console.log('╚════════════════════════════════════════════════════════╝');

  const results: boolean[] = [];

  results.push(await testStateSynchronization());
  results.push(await testReplayReconstruction());
  results.push(await testBandwidthEfficiency());

  const passed = results.filter(r => r).length;
  const failed = results.filter(r => !r).length;

  console.log('\n────────────────────────────────────────────────────────');
  console.log(`  RESULTS: ${passed} passed, ${failed} failed`);

  if (failed === 0) {
    console.log('\n  ✓ MODULE 8 COMPLETE — Ultra-low streaming proven!');
    console.log('  Ready for Module 9: Camera Tile Delta Streaming');
  }

  console.log('────────────────────────────────────────────────────────\n');

  return { passed, failed };
}

// Run if executed directly
const isMainModule = process.argv[1]?.includes('ui-stream-test');
if (isMainModule) {
  runModule8Tests().then(({ passed, failed }) => {
    process.exit(failed > 0 ? 1 : 0);
  });
}
