/**
 * Delta-State Fabric v0 — Module 9: Camera Stream Test Harness
 *
 * Proves state-based video streaming by simulating a static room
 * with one moving object. Pass conditions:
 * 1. Receiver scene matches sender within 1 tick
 * 2. avg bytes/sec < 1 KB/sec steady state
 * 3. Replay from deltas reconstructs identical scene
 * 4. Residual tile rate < 10% of tiles/sec under normal motion
 */

import { UUID, Delta, SceneTileData, SceneLightData } from './types';
import { CameraSceneStore } from './camera-surface';
import {
  CameraExtractor,
  CameraMetricsTracker,
  SimulatedFrame,
  DetectedBlob,
  TilePixels,
  buildBaseline,
  createCompactCameraDelta,
} from './camera-extractor';
import {
  CameraStreamReceiver,
  composeScene,
  scenesMatch,
  computeSceneHash,
} from './camera-renderer';
import { generateUUID, now, computeHash } from './delta';

// === TEST CONFIGURATION ===

const GRID_W = 8;
const GRID_H = 6;
const TILE_SIZE = 16;
const TEST_DURATION_TICKS = 100;

// === FRAME SIMULATION ===

/**
 * Generate baseline frame (static room)
 */
function generateBaselineFrame(): SimulatedFrame {
  const tiles = new Map<string, TilePixels>();

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      // Generate static pattern based on position
      const pixels: number[] = [];
      for (let i = 0; i < TILE_SIZE * TILE_SIZE; i++) {
        // Simple gradient + noise
        const base = 128 + (x * 10) - (y * 8);
        const noise = Math.random() * 10 - 5;
        pixels.push(Math.max(0, Math.min(255, base + noise)));
      }
      tiles.set(`${x},${y}`, pixels);
    }
  }

  return {
    tiles,
    globalBrightness: 0,
    colorTemp: 5500,
  };
}

/**
 * Generate frame with moving object
 */
function generateFrameWithObject(
  baseline: SimulatedFrame,
  objectX: number,
  objectY: number,
  lightingChange: number = 0
): { frame: SimulatedFrame; blob: DetectedBlob | null } {
  const tiles = new Map<string, TilePixels>();

  // Copy baseline tiles
  for (const [key, pixels] of baseline.tiles) {
    tiles.set(key, [...pixels]);
  }

  // Object occupies a 2x2 tile region
  const objectTiles: string[] = [];
  const roundX = Math.floor(objectX);
  const roundY = Math.floor(objectY);

  for (let dy = 0; dy < 2; dy++) {
    for (let dx = 0; dx < 2; dx++) {
      const tx = roundX + dx;
      const ty = roundY + dy;
      if (tx >= 0 && tx < GRID_W && ty >= 0 && ty < GRID_H) {
        const key = `${tx},${ty}`;
        objectTiles.push(key);

        // Modify tile where object is
        const pixels = tiles.get(key);
        if (pixels) {
          // Object is darker (person/pet shadow)
          for (let i = 0; i < pixels.length; i++) {
            pixels[i] = Math.max(0, pixels[i] - 40);
          }
        }
      }
    }
  }

  const blob: DetectedBlob | null = objectTiles.length > 0 ? {
    id: 'moving-object',
    x: roundX,
    y: roundY,
    tiles: objectTiles,
    brightness: -2, // Object is slightly darker
  } : null;

  return {
    frame: {
      tiles,
      globalBrightness: lightingChange,
      colorTemp: 5500 + lightingChange * 50,
    },
    blob,
  };
}

// === TEST HARNESS ===

interface TestHarness {
  surfaceId: UUID;
  senderStore: CameraSceneStore;
  receiverStore: CameraSceneStore;
  extractor: CameraExtractor;
  receiver: CameraStreamReceiver;
  senderMetrics: CameraMetricsTracker;
  tileIds: Map<string, UUID>;
  lightId: UUID;
  baselineFrame: SimulatedFrame;
  deltaLedger: Delta[];
}

/**
 * Create test harness with baseline
 */
function createTestHarness(): TestHarness {
  const surfaceId = generateUUID();
  const baselineFrame = generateBaselineFrame();

  // Build sender baseline
  const { store: senderStore, tileIds, lightId } = buildBaseline(
    baselineFrame,
    GRID_W,
    GRID_H,
    surfaceId
  );

  // Create receiver with identical baseline
  const receiverStore = new CameraSceneStore(surfaceId, GRID_W, GRID_H);
  const receiver = new CameraStreamReceiver(receiverStore);

  // Register same initial states on receiver
  for (const { id, state } of senderStore.getAllTiles()) {
    receiver.registerTile(id, state);
  }
  for (const { id, state } of senderStore.getAllLights()) {
    receiver.registerLight(id, state);
  }

  const senderMetrics = new CameraMetricsTracker();
  const extractor = new CameraExtractor(
    senderStore,
    baselineFrame,
    tileIds,
    lightId,
    senderMetrics,
    10 // residual threshold
  );

  return {
    surfaceId,
    senderStore,
    receiverStore,
    extractor,
    receiver,
    senderMetrics,
    tileIds,
    lightId,
    baselineFrame,
    deltaLedger: [],
  };
}

// === TESTS ===

/**
 * Test 1: State Synchronization
 * Receiver scene matches sender within 1 tick
 */
async function testStateSynchronization(): Promise<boolean> {
  console.log('\n=== Test 1: State Synchronization ===\n');

  const harness = createTestHarness();
  let allMatched = true;

  // Simulate moving object across screen
  for (let tick = 0; tick < TEST_DURATION_TICKS; tick++) {
    // Object moves diagonally
    const objectX = (tick * 0.1) % (GRID_W - 2);
    const objectY = Math.sin(tick * 0.1) * 2 + 2;

    // Occasional lighting change
    const lightChange = tick % 30 === 0 ? (Math.random() - 0.5) * 4 : 0;

    const { frame, blob } = generateFrameWithObject(
      harness.baselineFrame,
      objectX,
      objectY,
      lightChange
    );

    // Extract deltas
    const blobs = blob ? [blob] : [];
    const deltas = harness.extractor.extractDeltas(frame, blobs);

    // Apply to receiver
    for (const delta of deltas) {
      harness.deltaLedger.push(delta);
      const result = harness.receiver.applyDelta(delta);
      if (!result.success) {
        console.log(`❌ Delta rejected at tick ${tick}: ${result.reason}`);
        allMatched = false;
      }
    }

    // Compare scenes every 10 ticks
    if (tick % 10 === 0) {
      const senderScene = composeScene(harness.extractor.getStore());
      const receiverScene = composeScene(harness.receiver.getStore());

      if (!scenesMatch(senderScene, receiverScene)) {
        console.log(`❌ Scene mismatch at tick ${tick}`);
        allMatched = false;
      }
    }
  }

  // Final comparison
  const senderScene = composeScene(harness.extractor.getStore());
  const receiverScene = composeScene(harness.receiver.getStore());
  const finalMatch = scenesMatch(senderScene, receiverScene);

  if (finalMatch && allMatched) {
    console.log('✓ Receiver scene matches sender throughout simulation');
    console.log(`  Total deltas: ${harness.deltaLedger.length}`);
    return true;
  } else {
    console.log('✗ Scene synchronization failed');
    return false;
  }
}

/**
 * Test 2: Bandwidth Efficiency
 * avg bytes/sec < 1 KB/sec steady state
 */
async function testBandwidthEfficiency(): Promise<boolean> {
  console.log('\n=== Test 2: Bandwidth Efficiency ===\n');

  const harness = createTestHarness();
  let compactBytes = 0;
  let compactCount = 0;

  for (let tick = 0; tick < TEST_DURATION_TICKS; tick++) {
    const objectX = (tick * 0.1) % (GRID_W - 2);
    const objectY = Math.sin(tick * 0.1) * 2 + 2;
    const lightChange = tick % 30 === 0 ? (Math.random() - 0.5) * 4 : 0;

    const { frame, blob } = generateFrameWithObject(
      harness.baselineFrame,
      objectX,
      objectY,
      lightChange
    );

    const blobs = blob ? [blob] : [];
    const deltas = harness.extractor.extractDeltas(frame, blobs);

    for (const delta of deltas) {
      harness.deltaLedger.push(delta);
      harness.receiver.applyDelta(delta);

      // Measure compact format
      const entityType = delta.patch.some(p => p.path === '/shape_tiles' || p.path.includes('shape_tiles'))
        ? 'object'
        : delta.patch.some(p => p.path === '/color_temp')
          ? 'light'
          : 'tile';

      const compact = createCompactCameraDelta(delta, entityType as 'tile' | 'object' | 'light');
      const size = JSON.stringify(compact).length;
      compactBytes += size;
      compactCount++;
    }
  }

  const metrics = harness.senderMetrics.getMetrics();

  // Calculate bytes per second (assuming 1 tick = 100ms = 10 FPS)
  const durationSec = TEST_DURATION_TICKS * 0.1;
  const bytesPerSec = compactBytes / durationSec;
  const avgBytesPerDelta = compactCount > 0 ? compactBytes / compactCount : 0;

  console.log('  Full Format:');
  console.log(`    Deltas: ${metrics.deltas_sent}`);
  console.log(`    Total bytes: ${metrics.bytes_sent}`);
  console.log(`    Avg bytes/delta: ${metrics.avg_bytes_per_delta.toFixed(1)}`);

  console.log('\n  Compact Format:');
  console.log(`    Total bytes: ${compactBytes}`);
  console.log(`    Avg bytes/delta: ${avgBytesPerDelta.toFixed(1)}`);
  console.log(`    Bytes/sec: ${bytesPerSec.toFixed(1)}`);

  console.log('\n  Breakdown:');
  console.log(`    Object updates: ${metrics.object_updates}`);
  console.log(`    Light updates: ${metrics.light_updates}`);
  console.log(`    Residual tiles: ${metrics.residual_tiles_emitted}`);

  // Pass condition: < 1024 bytes/sec (1 KB/sec)
  const passed = bytesPerSec < 1024;

  if (passed) {
    console.log(`\n✓ Bandwidth efficiency: ${bytesPerSec.toFixed(1)} bytes/sec < 1024`);
    return true;
  } else {
    console.log(`\n✗ Bandwidth efficiency: ${bytesPerSec.toFixed(1)} bytes/sec >= 1024`);
    return false;
  }
}

/**
 * Test 3: Replay Reconstruction
 * Replay from deltas reconstructs identical scene
 */
async function testReplayReconstruction(): Promise<boolean> {
  console.log('\n=== Test 3: Replay Reconstruction ===\n');

  // Run simulation and collect deltas
  const harness = createTestHarness();

  for (let tick = 0; tick < 50; tick++) {
    const objectX = (tick * 0.1) % (GRID_W - 2);
    const objectY = Math.sin(tick * 0.1) * 2 + 2;

    const { frame, blob } = generateFrameWithObject(
      harness.baselineFrame,
      objectX,
      objectY,
      0
    );

    const blobs = blob ? [blob] : [];
    const deltas = harness.extractor.extractDeltas(frame, blobs);

    for (const delta of deltas) {
      harness.deltaLedger.push(delta);
      harness.receiver.applyDelta(delta);
    }
  }

  // Capture sender scene hash
  const senderScene = composeScene(harness.extractor.getStore());
  const senderHash = computeSceneHash(senderScene);

  // Create fresh receiver with baseline
  const freshReceiverStore = new CameraSceneStore(harness.surfaceId, GRID_W, GRID_H);
  const freshReceiver = new CameraStreamReceiver(freshReceiverStore);

  // Register baseline
  for (const { id, state } of harness.senderStore.getAllTiles()) {
    // Use original baseline state (before updates)
    const key = `${state.x},${state.y}`;
    const originalHash = computeHash(harness.baselineFrame.tiles.get(key) || []);
    const baselineState: SceneTileData = {
      ...state,
      hash: originalHash,
      brightness: 0,
      chroma: 0,
      is_residual: false,
    };
    freshReceiver.registerTile(id, baselineState);
  }

  // Register original light
  const originalLightState: SceneLightData = {
    surface_id: harness.surfaceId,
    region: 'GLOBAL',
    brightness: 0,
    color_temp: 5500,
    created_at: now(),
  };
  freshReceiver.registerLight(harness.lightId, originalLightState);

  // Replay deltas
  console.log(`  Replaying ${harness.deltaLedger.length} deltas...`);
  const { applied, rejected } = freshReceiver.replay(harness.deltaLedger);
  console.log(`  Applied: ${applied}, Rejected: ${rejected}`);

  // Compare scenes
  const replayedScene = composeScene(freshReceiver.getStore());
  const replayedHash = computeSceneHash(replayedScene);

  const match = senderHash === replayedHash;

  if (match && rejected === 0) {
    console.log('✓ Replay reconstruction successful');
    return true;
  } else {
    console.log('✗ Replay reconstruction failed');
    if (senderHash !== replayedHash) {
      console.log('  Scene hashes differ');
    }
    return false;
  }
}

/**
 * Test 4: Residual Tile Rate
 * < 10% of tiles/sec under normal motion
 */
async function testResidualTileRate(): Promise<boolean> {
  console.log('\n=== Test 4: Residual Tile Rate ===\n');

  const harness = createTestHarness();
  const totalTiles = GRID_W * GRID_H;

  for (let tick = 0; tick < TEST_DURATION_TICKS; tick++) {
    const objectX = (tick * 0.1) % (GRID_W - 2);
    const objectY = Math.sin(tick * 0.1) * 2 + 2;

    const { frame, blob } = generateFrameWithObject(
      harness.baselineFrame,
      objectX,
      objectY,
      0
    );

    const blobs = blob ? [blob] : [];
    harness.extractor.extractDeltas(frame, blobs);
  }

  const metrics = harness.senderMetrics.getMetrics();

  // Calculate residual rate
  const durationSec = TEST_DURATION_TICKS * 0.1;
  const residualsPerSec = metrics.residual_tiles_emitted / durationSec;
  const residualRatePercent = (residualsPerSec / totalTiles) * 100;

  console.log(`  Total tiles: ${totalTiles}`);
  console.log(`  Residual tiles emitted: ${metrics.residual_tiles_emitted}`);
  console.log(`  Residuals/sec: ${residualsPerSec.toFixed(2)}`);
  console.log(`  Residual rate: ${residualRatePercent.toFixed(2)}% of tiles/sec`);

  // Pass condition: < 10%
  const passed = residualRatePercent < 10;

  if (passed) {
    console.log(`\n✓ Residual tile rate: ${residualRatePercent.toFixed(2)}% < 10%`);
    return true;
  } else {
    console.log(`\n✗ Residual tile rate: ${residualRatePercent.toFixed(2)}% >= 10%`);
    return false;
  }
}

/**
 * Run all Module 9 tests
 */
export async function runModule9Tests(): Promise<{ passed: number; failed: number }> {
  console.log('\n╔════════════════════════════════════════════════════════╗');
  console.log('║   MODULE 9: CAMERA TILE DELTA STREAMING — PROOF TESTS  ║');
  console.log('╚════════════════════════════════════════════════════════╝');

  const results: boolean[] = [];

  results.push(await testStateSynchronization());
  results.push(await testBandwidthEfficiency());
  results.push(await testReplayReconstruction());
  results.push(await testResidualTileRate());

  const passed = results.filter(r => r).length;
  const failed = results.filter(r => !r).length;

  console.log('\n────────────────────────────────────────────────────────');
  console.log(`  RESULTS: ${passed} passed, ${failed} failed`);

  if (failed === 0) {
    console.log('\n  ✓ MODULE 9 COMPLETE — State-based video proven!');
    console.log('  Ultra-Low Streaming SDK v0 ready (Module 8 + 9)');
  }

  console.log('────────────────────────────────────────────────────────\n');

  return { passed, failed };
}

// Run if executed directly
const isMainModule = process.argv[1]?.includes('camera-stream-test');
if (isMainModule) {
  runModule9Tests().then(({ passed, failed }) => {
    process.exit(failed > 0 ? 1 : 0);
  });
}
