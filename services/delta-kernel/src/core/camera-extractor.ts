/**
 * Delta-State Fabric v0 — Module 9: Camera Extractor
 *
 * Baseline capture and extraction pipeline.
 * Converts frame changes to state deltas.
 */

import {
  UUID,
  Delta,
  JsonPatch,
  SceneTileData,
  SceneObjectData,
  SceneLightData,
  CameraStreamMetrics,
} from './types';
import {
  CameraSceneStore,
  validateTilePatch,
  validateObjectPatch,
  validateLightPatch,
  computeTileHash,
  computeTileEnergy,
} from './camera-surface';
import { generateUUID, now, computeHash, applyPatch } from './delta';

// === METRICS TRACKER ===

export class CameraMetricsTracker {
  private metrics: CameraStreamMetrics = {
    deltas_sent: 0,
    bytes_sent: 0,
    avg_bytes_per_delta: 0,
    residual_tiles_emitted: 0,
    object_updates: 0,
    light_updates: 0,
  };

  recordDelta(bytes: number, type: 'tile' | 'object' | 'light'): void {
    this.metrics.deltas_sent++;
    this.metrics.bytes_sent += bytes;
    this.metrics.avg_bytes_per_delta = this.metrics.bytes_sent / this.metrics.deltas_sent;

    if (type === 'tile') this.metrics.residual_tiles_emitted++;
    if (type === 'object') this.metrics.object_updates++;
    if (type === 'light') this.metrics.light_updates++;
  }

  getMetrics(): CameraStreamMetrics {
    return { ...this.metrics };
  }

  reset(): void {
    this.metrics = {
      deltas_sent: 0,
      bytes_sent: 0,
      avg_bytes_per_delta: 0,
      residual_tiles_emitted: 0,
      object_updates: 0,
      light_updates: 0,
    };
  }
}

// === SIMULATED FRAME DATA ===

/**
 * Simulated pixel tile (grayscale values 0-255)
 */
export type TilePixels = number[];

/**
 * Simulated frame (grid of tiles)
 */
export interface SimulatedFrame {
  tiles: Map<string, TilePixels>; // "x,y" -> pixels
  globalBrightness: number;
  colorTemp: number;
}

/**
 * Detected object (blob from motion segmentation)
 */
export interface DetectedBlob {
  id: string;
  x: number;
  y: number;
  tiles: string[]; // "x,y" keys
  brightness: number;
}

// === BASELINE BUILDER ===

/**
 * Build baseline from first frame
 */
export function buildBaseline(
  frame: SimulatedFrame,
  gridW: number,
  gridH: number,
  surfaceId: UUID
): {
  store: CameraSceneStore;
  tileIds: Map<string, UUID>;
  lightId: UUID;
} {
  const store = new CameraSceneStore(surfaceId, gridW, gridH);
  const tileIds = new Map<string, UUID>();
  const createdAt = now();

  // Create tiles
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const key = `${x},${y}`;
      const pixels = frame.tiles.get(key) || [];
      const hash = computeTileHash(pixels);
      const tileId = generateUUID();

      const tileState: SceneTileData = {
        surface_id: surfaceId,
        x,
        y,
        hash,
        brightness: 0,
        chroma: 0,
        is_residual: false,
        created_at: createdAt,
      };

      store.registerTile(tileId, tileState);
      tileIds.set(key, tileId);
    }
  }

  // Create global light
  const lightId = generateUUID();
  const lightState: SceneLightData = {
    surface_id: surfaceId,
    region: 'GLOBAL',
    brightness: frame.globalBrightness,
    color_temp: frame.colorTemp,
    created_at: createdAt,
  };
  store.registerLight(lightId, lightState);

  return { store, tileIds, lightId };
}

// === EXTRACTOR PIPELINE ===

export class CameraExtractor {
  private store: CameraSceneStore;
  private baselineTiles: Map<string, TilePixels>;
  private tileIds: Map<string, UUID>;
  private lightId: UUID;
  private objects: Map<string, UUID>; // blob ID -> object UUID
  private metrics: CameraMetricsTracker;
  private residualThreshold: number;

  constructor(
    store: CameraSceneStore,
    baselineFrame: SimulatedFrame,
    tileIds: Map<string, UUID>,
    lightId: UUID,
    metrics: CameraMetricsTracker,
    residualThreshold: number = 10
  ) {
    this.store = store;
    this.baselineTiles = new Map(baselineFrame.tiles);
    this.tileIds = tileIds;
    this.lightId = lightId;
    this.objects = new Map();
    this.metrics = metrics;
    this.residualThreshold = residualThreshold;
  }

  /**
   * Extract deltas from new frame
   */
  extractDeltas(frame: SimulatedFrame, detectedBlobs: DetectedBlob[]): Delta[] {
    const deltas: Delta[] = [];

    // 1. Lighting pass
    const lightDeltas = this.extractLightingDeltas(frame);
    deltas.push(...lightDeltas);

    // 2. Object pass (preferred)
    const objectDeltas = this.extractObjectDeltas(detectedBlobs);
    deltas.push(...objectDeltas);

    // 3. Residual tile pass (fallback for unexplained changes)
    const coveredTiles = new Set<string>();
    for (const blob of detectedBlobs) {
      for (const tileKey of blob.tiles) {
        coveredTiles.add(tileKey);
      }
    }

    const residualDeltas = this.extractResidualDeltas(frame, coveredTiles);
    deltas.push(...residualDeltas);

    return deltas;
  }

  /**
   * Extract lighting change deltas
   */
  private extractLightingDeltas(frame: SimulatedFrame): Delta[] {
    const deltas: Delta[] = [];
    const lightData = this.store.getLight(this.lightId);
    if (!lightData) return deltas;

    const { state, hash } = lightData;

    // Check brightness change
    if (Math.abs(frame.globalBrightness - state.brightness) > 0.5) {
      const patch: JsonPatch = {
        op: 'replace',
        path: '/brightness',
        value: Math.round(frame.globalBrightness),
      };

      const validation = validateLightPatch(patch);
      if (validation.valid) {
        const newState = applyPatch(state, [patch]) as SceneLightData;
        const newHash = computeHash(newState);

        const delta = this.createDelta(this.lightId, hash, [patch], newHash);
        this.store.updateLight(this.lightId, newState);
        this.metrics.recordDelta(JSON.stringify(delta).length, 'light');
        deltas.push(delta);
      }
    }

    // Check color temp change
    if (Math.abs(frame.colorTemp - state.color_temp) > 100) {
      const currentData = this.store.getLight(this.lightId);
      if (!currentData) return deltas;

      const patch: JsonPatch = {
        op: 'replace',
        path: '/color_temp',
        value: Math.round(frame.colorTemp),
      };

      const validation = validateLightPatch(patch);
      if (validation.valid) {
        const newState = applyPatch(currentData.state, [patch]) as SceneLightData;
        const newHash = computeHash(newState);

        const delta = this.createDelta(this.lightId, currentData.hash, [patch], newHash);
        this.store.updateLight(this.lightId, newState);
        this.metrics.recordDelta(JSON.stringify(delta).length, 'light');
        deltas.push(delta);
      }
    }

    return deltas;
  }

  /**
   * Extract object movement deltas
   */
  private extractObjectDeltas(detectedBlobs: DetectedBlob[]): Delta[] {
    const deltas: Delta[] = [];

    for (const blob of detectedBlobs) {
      let objectId = this.objects.get(blob.id);

      if (objectId) {
        // Existing object - update position
        const objData = this.store.getObject(objectId);
        if (!objData) continue;

        const { state, hash } = objData;
        const patches: JsonPatch[] = [];

        // Position changes
        if (state.x !== blob.x) {
          patches.push({ op: 'replace', path: '/x', value: blob.x });
        }
        if (state.y !== blob.y) {
          patches.push({ op: 'replace', path: '/y', value: blob.y });
        }

        // Velocity (computed from position change)
        const vx = blob.x - state.x;
        const vy = blob.y - state.y;
        if (state.vx !== vx) {
          patches.push({ op: 'replace', path: '/vx', value: vx });
        }
        if (state.vy !== vy) {
          patches.push({ op: 'replace', path: '/vy', value: vy });
        }

        // Brightness
        if (Math.abs(state.brightness - blob.brightness) > 0.5) {
          patches.push({ op: 'replace', path: '/brightness', value: Math.round(blob.brightness) });
        }

        if (patches.length > 0) {
          // Validate all patches
          const allValid = patches.every(p => validateObjectPatch(p).valid);
          if (allValid) {
            const newState = applyPatch(state, patches) as SceneObjectData;
            const newHash = computeHash(newState);

            const delta = this.createDelta(objectId, hash, patches, newHash);
            this.store.updateObject(objectId, newState);
            this.metrics.recordDelta(JSON.stringify(delta).length, 'object');
            deltas.push(delta);
          }
        }
      } else {
        // New object - create it
        objectId = generateUUID();

        // Get tile UUIDs for shape
        const shapeTiles: UUID[] = [];
        for (const tileKey of blob.tiles) {
          const tileId = this.tileIds.get(tileKey);
          if (tileId) shapeTiles.push(tileId);
        }

        const newState: SceneObjectData = {
          surface_id: this.store.getSurfaceId(),
          shape_tiles: shapeTiles,
          x: blob.x,
          y: blob.y,
          vx: 0,
          vy: 0,
          brightness: blob.brightness,
          visible: true,
          created_at: now(),
        };

        this.store.registerObject(objectId, newState);
        this.objects.set(blob.id, objectId);

        // Create delta for new object (full state as add operations)
        const patches: JsonPatch[] = Object.entries(newState).map(([key, value]) => ({
          op: 'add' as const,
          path: `/${key}`,
          value,
        }));

        const newHash = computeHash(newState);
        const delta = this.createDelta(objectId, '0'.repeat(64), patches, newHash);
        this.metrics.recordDelta(JSON.stringify(delta).length, 'object');
        deltas.push(delta);
      }
    }

    return deltas;
  }

  /**
   * Extract residual tile deltas (fallback for unexplained changes)
   */
  private extractResidualDeltas(frame: SimulatedFrame, coveredTiles: Set<string>): Delta[] {
    const deltas: Delta[] = [];

    for (const [key, pixels] of frame.tiles) {
      // Skip tiles covered by objects
      if (coveredTiles.has(key)) continue;

      const baseline = this.baselineTiles.get(key);
      if (!baseline) continue;

      // Compute residual energy
      const energy = computeTileEnergy(pixels, baseline);

      // If significant change, emit residual
      if (energy > this.residualThreshold) {
        const tileId = this.tileIds.get(key);
        if (!tileId) continue;

        const tileData = this.store.getTile(tileId);
        if (!tileData) continue;

        const { state, hash } = tileData;
        const patches: JsonPatch[] = [];

        // Update hash (residual tile)
        const newTileHash = computeTileHash(pixels);
        if (state.hash !== newTileHash) {
          patches.push({ op: 'replace', path: '/hash', value: newTileHash });
        }

        // Compute brightness delta
        const avgBaseline = baseline.reduce((a, b) => a + b, 0) / baseline.length;
        const avgCurrent = pixels.reduce((a, b) => a + b, 0) / pixels.length;
        const brightnessDelta = Math.round((avgCurrent - avgBaseline) / 16); // Scale to -8..+8
        if (state.brightness !== brightnessDelta) {
          patches.push({ op: 'replace', path: '/brightness', value: Math.max(-8, Math.min(8, brightnessDelta)) });
        }

        // Mark as residual
        if (!state.is_residual) {
          patches.push({ op: 'replace', path: '/is_residual', value: true });
        }

        if (patches.length > 0) {
          const allValid = patches.every(p => validateTilePatch(p).valid);
          if (allValid) {
            const newState = applyPatch(state, patches) as SceneTileData;
            const newHash = computeHash(newState);

            const delta = this.createDelta(tileId, hash, patches, newHash);
            this.store.updateTile(tileId, newState);
            this.metrics.recordDelta(JSON.stringify(delta).length, 'tile');
            deltas.push(delta);
          }
        }
      }
    }

    return deltas;
  }

  /**
   * Create a delta
   */
  private createDelta(entityId: UUID, prevHash: string, patches: JsonPatch[], newHash: string): Delta {
    return {
      delta_id: generateUUID(),
      entity_id: entityId,
      timestamp: now(),
      author: 'system',
      patch: patches,
      prev_hash: prevHash,
      new_hash: newHash,
    };
  }

  /**
   * Get current store
   */
  getStore(): CameraSceneStore {
    return this.store;
  }
}

// === COMPACT DELTA FORMAT ===

/**
 * Compact camera delta for wire transmission
 */
export interface CompactCameraDelta {
  d: string;    // delta_id (8 char)
  e: string;    // entity_id (4 char short)
  t: number;    // timestamp
  type: 'T' | 'O' | 'L';  // Tile, Object, Light
  p: Array<{ o: string; k: string; v: unknown }>; // op, key, value
  ph: string;   // prev_hash (8 char)
  nh: string;   // new_hash (8 char)
}

// ID shortening
const shortIdMap = new Map<UUID, string>();
let shortIdCounter = 0;

function getShortId(fullId: UUID): string {
  let short = shortIdMap.get(fullId);
  if (!short) {
    short = (++shortIdCounter).toString(16).padStart(4, '0');
    shortIdMap.set(fullId, short);
  }
  return short;
}

/**
 * Create compact delta for wire transmission
 */
export function createCompactCameraDelta(
  delta: Delta,
  entityType: 'tile' | 'object' | 'light'
): CompactCameraDelta {
  const typeMap = { tile: 'T' as const, object: 'O' as const, light: 'L' as const };

  return {
    d: delta.delta_id.slice(0, 8),
    e: getShortId(delta.entity_id),
    t: delta.timestamp,
    type: typeMap[entityType],
    p: delta.patch.map(p => ({
      o: p.op[0],                          // 'r' for replace, 'a' for add
      k: p.path.split('/').pop() || '',    // Just the key
      v: p.value,
    })),
    ph: delta.prev_hash.slice(0, 8),
    nh: delta.new_hash.slice(0, 8),
  };
}
