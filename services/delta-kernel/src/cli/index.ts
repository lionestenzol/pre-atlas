#!/usr/bin/env node
/**
 * Delta-State Fabric — CLI Entry Point
 *
 * Run with: npx tsx src/cli/index.ts
 */

import * as path from 'path';
import * as os from 'os';
import { DeltaApp } from './app';

const DEFAULT_DATA_DIR = path.join(os.homedir(), '.delta-fabric');

async function main() {
  // Parse command line args
  const args = process.argv.slice(2);
  let dataDir = DEFAULT_DATA_DIR;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--data' && args[i + 1]) {
      dataDir = args[i + 1];
      i++;
    } else if (args[i] === '--help' || args[i] === '-h') {
      printHelp();
      process.exit(0);
    }
  }

  console.log('Starting Delta-State Fabric...');
  console.log(`Data directory: ${dataDir}`);
  console.log('');

  const app = new DeltaApp(dataDir);
  await app.start();
}

function printHelp() {
  console.log(`
Delta-State Fabric v0 — CLI

Usage: npx tsx src/cli/index.ts [options]

Options:
  --data <dir>    Data directory (default: ~/.delta-fabric)
  --help, -h      Show this help

Controls:
  ↑/↓             Navigate actions
  Enter           Execute selected action
  1-7             Quick select action by number
  n               Create new task
  r               Run preparation engine
  s               Signal update (sleep, mood, etc.)
  q               Quit

Modes:
  RECOVER         Rest and recovery (restricted actions)
  CLOSE_LOOPS     Clear pending items
  BUILD           Create new things
  COMPOUND        Extend existing work
  SCALE           Delegate and automate
`);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
