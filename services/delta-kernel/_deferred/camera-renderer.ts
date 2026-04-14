/**
 * Delta-State Fabric v0 — Module 9: Camera Renderer
 *
 * Deterministic scene composition from state.
 * Applies deltas and renders scene.
 */

import {
  UUID,
  Delta,
  SceneTileData,
  SceneObjectData,
  SceneLightData,
} from './types';
import {
  CameraSceneStore,
  validateTilePatch,
  validateObjectPatch,
  validateLightPatch,
} from './camera-surface';
import { computeHash, applyPatch } from './delta';

// === RECEIVER ===

/**
 * Camera stream receiver - applies deltas and maintains scene state
 */
export class CameraStreamReceiver {
  private store: CameraSceneStore;
  private entityTypes: Map<UUID, 'tile' | 'object' | 'light'> = new Map();

  constructor(store: CameraSceneStore) {
    this.store = store;
  }

  /**
   * Register entity type for delta validation
   */
  registerEntityType(entityId: UUID, type: 'tile' | 'object' | 'light'): void {
    this.entityTypes.set(entityId, type);
  }

  /**
   * Register initial tile state
   */
  registerTile(id: UUID, state: SceneTileData): void {
    this.store.registerTile(id, state);
    this.entityTypes.set(id, 'tile');
  }

  /**
   * Register initial object state
   */
  registerObject(id: UUID, state: SceneObjectData): void {
    this.store.registerObject(id, state);
    this.entityTypes.set(id, 'object');
  }

  /**
   * Register initial light state
   */
  registerLight(id: UUID, state: SceneLightData): void {
    this.store.registerLight(id, state);
    this.entityTypes.set(id, 'light');
  }

  /**
   * Apply a delta from sender
   */
  applyDelta(delta: Delta): { success: boolean; reason?: string } {
    const entityType = this.entityTypes.get(delta.entity_id);

    // Handle new entity creation
    if (!entityType) {
      // Check if this is a creation delta (first patch is 'add' to root)
      if (delta.patch.length > 0 && delta.patch[0].op === 'add') {
        // Infer type from patches
        const hasShapeTiles = delta.patch.some(p => p.path === '/shape_tiles');
        const hasColorTemp = delta.patch.some(p => p.path === '/color_temp');
        const hasTileHash = delta.patch.some(p => p.path === '/hash' && delta.patch.some(q => q.path === '/x'));

        if (hasShapeTiles) {
          // It's an object
          const newState = this.reconstructState(delta.patch) as SceneObjectData;
          this.store.registerObject(delta.entity_id, newState);
          this.entityTypes.set(delta.entity_id, 'object');
          return { success: true };
        } else if (hasColorTemp) {
          // It's a light
          const newState = this.reconstructState(delta.patch) as SceneLightData;
          this.store.registerLight(delta.entity_id, newState);
          this.entityTypes.set(delta.entity_id, 'light');
          return { success: true };
        } else if (hasTileHash) {
          // It's a tile
          const newState = this.reconstructState(delta.patch) as SceneTileData;
          this.store.registerTile(delta.entity_id, newState);
          this.entityTypes.set(delta.entity_id, 'tile');
          return { success: true };
        }
      }
      return { success: false, reason: 'ENTITY_UNKNOWN' };
    }

    // Get current state and validate
    let currentData: { state: unknown; hash: string } | undefined;

    switch (entityType) {
      case 'tile':
        currentData = this.store.getTile(delta.entity_id);
        break;
      case 'object':
        currentData = this.store.getObject(delta.entity_id);
        break;
      case 'light':
        currentData = this.store.getLight(delta.entity_id);
        break;
    }

    if (!currentData) {
      return { success: false, reason: 'ENTITY_NOT_FOUND' };
    }

    // Verify hash chain
    if (currentData.hash !== delta.prev_hash) {
      return { success: false, reason: 'HASH_CHAIN_BROKEN' };
    }

    // Validate patches based on entity type
    for (const patch of delta.patch) {
      let validation: { valid: boolean; reason?: string };

      switch (entityType) {
        case 'tile':
          validation = validateTilePatch(patch);
          break;
        case 'object':
          validation = validateObjectPatch(patch);
          break;
        case 'light':
          validation = validateLightPatch(patch);
          break;
      }

      if (!validation.valid) {
        return { success: false, reason: validation.reason || 'SCHEMA_INVALID' };
      }
    }

    // Apply patches
    const newState = applyPatch(currentData.state as Record<string, unknown>, delta.patch);
    const computedHash = computeHash(newState);

    // Verify new hash
    if (computedHash !== delta.new_hash) {
      return { success: false, reason: 'HASH_MISMATCH' };
    }

    // Update store
    switch (entityType) {
      case 'tile':
        this.store.updateTile(delta.entity_id, newState as SceneTileData);
        break;
      case 'object':
        this.store.updateObject(delta.entity_id, newState as SceneObjectData);
        break;
      case 'light':
        this.store.updateLight(delta.entity_id, newState as SceneLightData);
        break;
    }

    return { success: true };
  }

  /**
   * Reconstruct state from creation patches
   */
  private reconstructState(patches: Delta['patch']): unknown {
    const state: Record<string, unknown> = {};
    for (const patch of patches) {
      if (patch.op === 'add') {
        const key = patch.path.slice(1); // Remove leading '/'
        state[key] = patch.value;
      }
    }
    return state;
  }

  /**
   * Replay deltas from ledger
   */
  replay(deltas: Delta[]): { applied: number; rejected: number } {
    let applied = 0;
    let rejected = 0;

    // Sort by timestamp
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

  /**
   * Get the scene store
   */
  getStore(): CameraSceneStore {
    return this.store;
  }
}

// === DETERMINISTIC RENDERER ===

/**
 * Rendered tile with applied adjustments
 */
export interface RenderedTile {
  x: number;
  y: number;
  brightness: number;  // Final brightness (-16..+16 after light)
  isObject: boolean;
  isResidual: boolean;
  hash: string;
}

/**
 * Compose scene from state (deterministic)
 */
export function composeScene(store: CameraSceneStore): RenderedTile[][] {
  const { w: gridW, h: gridH } = store.getGridSize();

  // Initialize grid
  const scene: RenderedTile[][] = [];
  for (let y = 0; y < gridH; y++) {
    scene[y] = [];
    for (let x = 0; x < gridW; x++) {
      scene[y][x] = {
        x,
        y,
        brightness: 0,
        isObject: false,
        isResidual: false,
        hash: '',
      };
    }
  }

  // 1. Apply baseline tiles
  for (const { state } of store.getAllTiles()) {
    if (state.x >= 0 && state.x < gridW && state.y >= 0 && state.y < gridH) {
      scene[state.y][state.x] = {
        x: state.x,
        y: state.y,
        brightness: state.brightness,
        isObject: false,
        isResidual: state.is_residual,
        hash: state.hash,
      };
    }
  }

  // 2. Apply global and regional light adjustments
  for (const { state: light } of store.getAllLights()) {
    if (light.region === 'GLOBAL') {
      // Apply to all tiles
      for (let y = 0; y < gridH; y++) {
        for (let x = 0; x < gridW; x++) {
          scene[y][x].brightness += light.brightness;
        }
      }
    } else {
      // Apply to region
      const region = light.region;
      for (let y = region.y; y < Math.min(region.y + region.h, gridH); y++) {
        for (let x = region.x; x < Math.min(region.x + region.w, gridW); x++) {
          if (x >= 0 && y >= 0) {
            scene[y][x].brightness += light.brightness;
          }
        }
      }
    }
  }

  // 3. Draw objects (mark tiles as part of object)
  for (const { state: obj } of store.getAllObjects()) {
    if (!obj.visible) continue;

    // For each shape tile, mark the position offset by object's x,y
    for (const tileId of obj.shape_tiles) {
      const tileData = store.getTile(tileId);
      if (!tileData) continue;

      const renderX = obj.x + tileData.state.x;
      const renderY = obj.y + tileData.state.y;

      if (renderX >= 0 && renderX < gridW && renderY >= 0 && renderY < gridH) {
        scene[renderY][renderX].isObject = true;
        scene[renderY][renderX].brightness += obj.brightness;
      }
    }
  }

  // Clamp brightness values
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      scene[y][x].brightness = Math.max(-16, Math.min(16, scene[y][x].brightness));
    }
  }

  return scene;
}

/**
 * Render scene to terminal (ASCII visualization)
 */
export function renderSceneToTerminal(scene: RenderedTile[][]): string {
  const lines: string[] = [];
  const chars = ' ░▒▓█';

  for (const row of scene) {
    let line = '';
    for (const tile of row) {
      // Map brightness to character
      const normalized = (tile.brightness + 16) / 32; // 0..1
      const charIndex = Math.floor(normalized * (chars.length - 1));

      if (tile.isObject) {
        // Objects shown with color
        line += `\x1b[33m${chars[charIndex]}\x1b[0m`;
      } else if (tile.isResidual) {
        // Residuals shown with different color
        line += `\x1b[36m${chars[charIndex]}\x1b[0m`;
      } else {
        line += chars[charIndex];
      }
    }
    lines.push(line);
  }

  return lines.join('\n');
}

/**
 * Compare two scenes for equality
 */
export function scenesMatch(a: RenderedTile[][], b: RenderedTile[][]): boolean {
  if (a.length !== b.length) return false;

  for (let y = 0; y < a.length; y++) {
    if (a[y].length !== b[y].length) return false;

    for (let x = 0; x < a[y].length; x++) {
      if (
        a[y][x].brightness !== b[y][x].brightness ||
        a[y][x].isObject !== b[y][x].isObject ||
        a[y][x].isResidual !== b[y][x].isResidual ||
        a[y][x].hash !== b[y][x].hash
      ) {
        return false;
      }
    }
  }

  return true;
}

/**
 * Compute scene hash for comparison
 */
export function computeSceneHash(scene: RenderedTile[][]): string {
  const data = scene.map(row =>
    row.map(t => `${t.brightness}:${t.isObject}:${t.isResidual}:${t.hash.slice(0, 8)}`).join(',')
  ).join('|');
  return computeHash(data);
}
