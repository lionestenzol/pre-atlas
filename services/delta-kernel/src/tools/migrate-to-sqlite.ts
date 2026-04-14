/**
 * Migration Script: JSON files → SQLite
 *
 * Reads existing entities.json + deltas.json from .delta-fabric/
 * and imports them into state.db (SQLite with WAL mode).
 *
 * After successful migration, renames old files to .bak.
 *
 * Usage: tsx src/tools/migrate-to-sqlite.ts [--data-dir <path>]
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { Storage } from '../cli/sqlite-storage';
import { Entity, Delta } from '../core/types';

const dataDir = process.argv.includes('--data-dir')
  ? process.argv[process.argv.indexOf('--data-dir') + 1]
  : process.env.DELTA_DATA_DIR || path.join(os.homedir(), '.delta-fabric');

const entitiesFile = path.join(dataDir, 'entities.json');
const deltasFile = path.join(dataDir, 'deltas.json');
const dbFile = path.join(dataDir, 'state.db');

console.log(`Migration: JSON → SQLite`);
console.log(`  Data dir: ${dataDir}`);

// Check if DB already exists
if (fs.existsSync(dbFile)) {
  console.log(`  state.db already exists. Skipping migration.`);
  console.log(`  To re-migrate, delete ${dbFile} first.`);
  process.exit(0);
}

// Check source files
const hasEntities = fs.existsSync(entitiesFile);
const hasDeltas = fs.existsSync(deltasFile);

if (!hasEntities && !hasDeltas) {
  console.log(`  No JSON files found. Creating empty database.`);
  new Storage({ dataDir });
  console.log(`  Done. Empty state.db created.`);
  process.exit(0);
}

// Load existing data
let entityEntries: Array<[string, { entity: Entity; state: unknown }]> = [];
let deltas: Delta[] = [];

if (hasEntities) {
  try {
    const raw = fs.readFileSync(entitiesFile, 'utf-8');
    entityEntries = JSON.parse(raw) as Array<[string, { entity: Entity; state: unknown }]>;
    console.log(`  Loaded ${entityEntries.length} entities from entities.json`);
  } catch (e) {
    console.error(`  Failed to read entities.json: ${(e as Error).message}`);
    process.exit(1);
  }
}

if (hasDeltas) {
  try {
    const raw = fs.readFileSync(deltasFile, 'utf-8');
    deltas = JSON.parse(raw) as Delta[];
    console.log(`  Loaded ${deltas.length} deltas from deltas.json (${(raw.length / 1024 / 1024).toFixed(2)} MB)`);
  } catch (e) {
    console.error(`  Failed to read deltas.json: ${(e as Error).message}`);
    process.exit(1);
  }
}

// Create SQLite storage and import
const storage = new Storage({ dataDir });

console.log(`  Importing entities...`);
for (const [, { entity, state }] of entityEntries) {
  storage.saveEntity(entity, state);
}

console.log(`  Importing deltas (this may take a moment)...`);
if (deltas.length > 0) {
  storage.appendDeltas(deltas);
}

// Verify counts
const stats = storage.getStats();
console.log(`  Verification: ${stats.entities} entities, ${stats.deltas} deltas, ${(stats.bytes / 1024).toFixed(1)} KB`);

if (stats.entities !== entityEntries.length) {
  console.error(`  Entity count mismatch! Expected ${entityEntries.length}, got ${stats.entities}`);
  process.exit(1);
}
if (stats.deltas !== deltas.length) {
  console.error(`  Delta count mismatch! Expected ${deltas.length}, got ${stats.deltas}`);
  process.exit(1);
}

// Rename old files to .bak
if (hasEntities) {
  fs.renameSync(entitiesFile, entitiesFile + '.bak');
  console.log(`  Renamed entities.json → entities.json.bak`);
}
if (hasDeltas) {
  fs.renameSync(deltasFile, deltasFile + '.bak');
  console.log(`  Renamed deltas.json → deltas.json.bak`);
}

storage.close();
console.log(`  Migration complete. Database: ${dbFile}`);
