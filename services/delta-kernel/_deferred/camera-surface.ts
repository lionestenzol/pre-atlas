/**
 * Delta-State Fabric v0 — Module 9: Camera Surface
 *
 * Schemas and validators for camera tile delta streaming.
 * Scene state deltas, not frames.
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Entity,
  Delta,
  JsonPatch,
  CameraSurfaceData,
  SceneTileData,
  SceneObjectData,
  SceneLightData,
  CameraTickData,
  LightRegion,
  RejectReason,
} from './types';
import { createEntity, now, generateUUID, computeHash } from './delta';

// === SCHEMA VALIDATORS ===

/**
 * Validate brightness value (-8..+8 for tiles, -16..+16 for lights)
 */
function validateBrightness(value: number, range: number): boolean {
  return typeof value === 'number' && value >= -range && value <= range;
}

/**
 * Validate chroma value (-8..+8)
 */
function validateChroma(value: number): boolean {
  return typeof value === 'number' && value >= -8 && value <= 8;
}

/**
 * Validate color temperature (1000K - 10000K typical range)
 */
function validateColorTemp(value: number): boolean {
  return typeof value === 'number' && value >= 1000 && value <= 10000;
}

/**
 * Validate grid position
 */
function validateGridPos(x: number, y: number, gridW: number, gridH: number): boolean {
  return x >= 0 && x < gridW && y >= 0 && y < gridH;
}

/**
 * Validate light region
 */
function validateLightRegion(region: LightRegion): boolean {
  if (region === 'GLOBAL') return true;
  if (typeof region === 'object') {
    return (
      typeof region.x === 'number' &&
      typeof region.y === 'number' &&
      typeof region.w === 'number' &&
      typeof region.h === 'number' &&
      region.w > 0 && region.h > 0
    );
  }
  return false;
}

// === DELTA VALIDATION (Streaming Contract) ===

/**
 * Allowed paths for SceneTileData
 */
const TILE_ALLOWED_PATHS = new Set([
  '/hash',
  '/brightness',
  '/chroma',
  '/is_residual',
]);

/**
 * Allowed paths for SceneObjectData
 */
const OBJECT_ALLOWED_PATHS = new Set([
  '/x',
  '/y',
  '/vx',
  '/vy',
  '/brightness',
  '/visible',
  '/shape_tiles/-',
  '/shape_tiles',
]);

/**
 * Allowed paths for SceneLightData
 */
const LIGHT_ALLOWED_PATHS = new Set([
  '/brightness',
  '/color_temp',
]);

/**
 * Validate a tile delta patch
 */
export function validateTilePatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!TILE_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/brightness' && !validateBrightness(value as number, 8)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/chroma' && !validateChroma(value as number)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/hash' && typeof value !== 'string') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/is_residual' && typeof value !== 'boolean') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

/**
 * Validate an object delta patch
 */
export function validateObjectPatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  // Handle shape_tiles array operations
  if (path.startsWith('/shape_tiles/')) {
    if (path === '/shape_tiles/-' && op === 'add') {
      if (typeof value !== 'string') {
        return { valid: false, reason: 'SCHEMA_INVALID' };
      }
      return { valid: true };
    }
    if (/^\/shape_tiles\/\d+$/.test(path) && op === 'remove') {
      return { valid: true };
    }
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (!OBJECT_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if ((path === '/x' || path === '/y' || path === '/vx' || path === '/vy') && typeof value !== 'number') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/brightness' && !validateBrightness(value as number, 8)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/visible' && typeof value !== 'boolean') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

/**
 * Validate a light delta patch
 */
export function validateLightPatch(patch: JsonPatch): { valid: boolean; reason?: RejectReason } {
  const { op, path, value } = patch;

  if (!LIGHT_ALLOWED_PATHS.has(path)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (op !== 'replace') {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/brightness' && !validateBrightness(value as number, 16)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  if (path === '/color_temp' && !validateColorTemp(value as number)) {
    return { valid: false, reason: 'SCHEMA_INVALID' };
  }

  return { valid: true };
}

// === ENTITY CREATION ===

/**
 * Create a new Camera Surface
 */
export async function createCameraSurface(
  name: string,
  gridW: number,
  gridH: number,
  tileSize: number
): Promise<{ entity: Entity; state: CameraSurfaceData; delta: Delta }> {
  const state: CameraSurfaceData = {
    name,
    grid_w: gridW,
    grid_h: gridH,
    tile_size: tileSize,
    created_at: now(),
  };

  return createEntity('camera_surface', state);
}

/**
 * Create a Scene Tile
 */
export async function createSceneTile(
  surfaceId: UUID,
  x: number,
  y: number,
  hash: SHA256,
  brightness: number = 0,
  chroma: number = 0,
  isResidual: boolean = false
): Promise<{ entity: Entity; state: SceneTileData; delta: Delta }> {
  const state: SceneTileData = {
    surface_id: surfaceId,
    x,
    y,
    hash,
    brightness,
    chroma,
    is_residual: isResidual,
    created_at: now(),
  };

  return createEntity('scene_tile', state);
}

/**
 * Create a Scene Object
 */
export async function createSceneObject(
  surfaceId: UUID,
  shapeTiles: UUID[],
  x: number,
  y: number,
  vx: number = 0,
  vy: number = 0,
  brightness: number = 0
): Promise<{ entity: Entity; state: SceneObjectData; delta: Delta }> {
  const state: SceneObjectData = {
    surface_id: surfaceId,
    shape_tiles: shapeTiles,
    x,
    y,
    vx,
    vy,
    brightness,
    visible: true,
    created_at: now(),
  };

  return createEntity('scene_object', state);
}

/**
 * Create a Scene Light
 */
export async function createSceneLight(
  surfaceId: UUID,
  region: LightRegion,
  brightness: number = 0,
  colorTemp: number = 5500
): Promise<{ entity: Entity; state: SceneLightData; delta: Delta }> {
  const state: SceneLightData = {
    surface_id: surfaceId,
    region,
    brightness,
    color_temp: colorTemp,
    created_at: now(),
  };

  return createEntity('scene_light', state);
}

/**
 * Create a Camera Tick
 */
export async function createCameraTick(
  surfaceId: UUID,
  tick: number
): Promise<{ entity: Entity; state: CameraTickData; delta: Delta }> {
  const state: CameraTickData = {
    surface_id: surfaceId,
    tick,
    created_at: now(),
  };

  return createEntity('camera_tick', state);
}

// === TILE HASH COMPUTATION ===

/**
 * Compute hash for tile content (simulated - would be actual pixel data)
 */
export function computeTileHash(tileData: number[]): SHA256 {
  return computeHash(tileData);
}

/**
 * Compute tile energy (for residual detection)
 */
export function computeTileEnergy(current: number[], baseline: number[]): number {
  if (current.length !== baseline.length) return Infinity;

  let energy = 0;
  for (let i = 0; i < current.length; i++) {
    const diff = current[i] - baseline[i];
    energy += diff * diff;
  }
  return Math.sqrt(energy / current.length);
}

// === SCENE STORE ===

/**
 * Store for camera scene state
 */
export class CameraSceneStore {
  private tiles: Map<UUID, { state: SceneTileData; hash: string }> = new Map();
  private objects: Map<UUID, { state: SceneObjectData; hash: string }> = new Map();
  private lights: Map<UUID, { state: SceneLightData; hash: string }> = new Map();
  private surfaceId: UUID;
  private gridW: number;
  private gridH: number;

  constructor(surfaceId: UUID, gridW: number, gridH: number) {
    this.surfaceId = surfaceId;
    this.gridW = gridW;
    this.gridH = gridH;
  }

  registerTile(id: UUID, state: SceneTileData): void {
    const hash = computeHash(state);
    this.tiles.set(id, { state, hash });
  }

  registerObject(id: UUID, state: SceneObjectData): void {
    const hash = computeHash(state);
    this.objects.set(id, { state, hash });
  }

  registerLight(id: UUID, state: SceneLightData): void {
    const hash = computeHash(state);
    this.lights.set(id, { state, hash });
  }

  getTile(id: UUID): { state: SceneTileData; hash: string } | undefined {
    return this.tiles.get(id);
  }

  getObject(id: UUID): { state: SceneObjectData; hash: string } | undefined {
    return this.objects.get(id);
  }

  getLight(id: UUID): { state: SceneLightData; hash: string } | undefined {
    return this.lights.get(id);
  }

  getTileAt(x: number, y: number): { id: UUID; state: SceneTileData; hash: string } | undefined {
    for (const [id, data] of this.tiles) {
      if (data.state.x === x && data.state.y === y) {
        return { id, ...data };
      }
    }
    return undefined;
  }

  updateTile(id: UUID, newState: SceneTileData): void {
    const newHash = computeHash(newState);
    this.tiles.set(id, { state: newState, hash: newHash });
  }

  updateObject(id: UUID, newState: SceneObjectData): void {
    const newHash = computeHash(newState);
    this.objects.set(id, { state: newState, hash: newHash });
  }

  updateLight(id: UUID, newState: SceneLightData): void {
    const newHash = computeHash(newState);
    this.lights.set(id, { state: newState, hash: newHash });
  }

  getAllTiles(): Array<{ id: UUID; state: SceneTileData; hash: string }> {
    return Array.from(this.tiles.entries()).map(([id, data]) => ({ id, ...data }));
  }

  getAllObjects(): Array<{ id: UUID; state: SceneObjectData; hash: string }> {
    return Array.from(this.objects.entries()).map(([id, data]) => ({ id, ...data }));
  }

  getAllLights(): Array<{ id: UUID; state: SceneLightData; hash: string }> {
    return Array.from(this.lights.entries()).map(([id, data]) => ({ id, ...data }));
  }

  getGridSize(): { w: number; h: number } {
    return { w: this.gridW, h: this.gridH };
  }

  getSurfaceId(): UUID {
    return this.surfaceId;
  }

  getResidualCount(): number {
    let count = 0;
    for (const { state } of this.tiles.values()) {
      if (state.is_residual) count++;
    }
    return count;
  }
}
