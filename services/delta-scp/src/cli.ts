// Delta SCP · standalone CLI — compress a repo, optionally focus it on a live
// state anchor, and route the result to the flue (droplist). No queue/Supabase.
//
//   npm run compress -- <repo> [out.json]
//   npm run compress -- <repo> --anchor src/auth/login.ts --md
//   npm run compress -- <repo> --trace error.log --flue
//
// Flags (all optional):
//   --anchor <p>      anchor a file path (repeatable, or comma-separated)
//   --symbol <name>   anchor a symbol by name (repeatable, or comma-separated)
//   --trace <file>    read an error/tool trace; paths in it become anchors
//   --prune           force pruning (implied by any --anchor/--symbol/--trace)
//   --md              emit Markdown (the flue payload) instead of JSON
//   --flue [dir]      write the Markdown drop into the flue inbox (default: config)
//
// Without any anchor flag it behaves exactly as before: a full compressed map.

import { readFile, writeFile } from 'node:fs/promises';
import { loadConfig } from './config.js';
import { compressRepository } from './source.js';
import { pruneMap, type AnchorSpec } from './prune.js';
import { renderFlueMarkdown, emitToFlue } from './flue.js';

interface CliArgs {
  target?: string;
  out?: string;
  anchorPaths: string[];
  anchorSymbols: string[];
  traceFile?: string;
  prune: boolean;
  md: boolean;
  flue: boolean;
  flueDir?: string;
}

function splitList(v: string): string[] {
  return v.split(',').map((s) => s.trim()).filter(Boolean);
}

function parseArgs(argv: string[]): CliArgs {
  const a: CliArgs = { anchorPaths: [], anchorSymbols: [], prune: false, md: false, flue: false };
  const positionals: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case '--anchor': a.anchorPaths.push(...splitList(argv[++i] ?? '')); break;
      case '--symbol': a.anchorSymbols.push(...splitList(argv[++i] ?? '')); break;
      case '--trace': a.traceFile = argv[++i]; break;
      case '--prune': a.prune = true; break;
      case '--md': a.md = true; break;
      case '--flue': {
        a.flue = true;
        const next = argv[i + 1];
        if (next && !next.startsWith('--')) a.flueDir = argv[++i]; // optional dir
        break;
      }
      default: positionals.push(arg);
    }
  }
  a.target = positionals[0];
  a.out = positionals[1];
  return a;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.target) {
    console.error('usage: npm run compress -- <repo> [out] [--anchor p] [--symbol s] [--trace f] [--md] [--flue [dir]]');
    process.exit(2);
  }

  const config = loadConfig();
  const compressed = await compressRepository(args.target, config);

  const anchorRequested =
    args.prune || args.anchorPaths.length > 0 || args.anchorSymbols.length > 0 || !!args.traceFile;

  let map: typeof compressed | ReturnType<typeof pruneMap> = compressed;
  if (anchorRequested) {
    const spec: AnchorSpec = { paths: args.anchorPaths, symbols: args.anchorSymbols };
    if (args.traceFile) spec.trace = await readFile(args.traceFile, 'utf8');
    map = pruneMap(compressed, spec);
    if (!map.stats.anchored) {
      console.error('[delta-scp] warning: no anchors resolved — emitting the full map unpruned');
    }
  }

  // The flue: render Markdown and drop it for the Chainer.
  if (args.flue) {
    const markdown = renderFlueMarkdown(map);
    const result = await emitToFlue(markdown, map, args.flueDir ?? config.flueDir);
    console.error(`[delta-scp] flue drop -> ${result.path} (${result.bytes} bytes)`);
    if (!args.out && !args.md) return; // flue was the whole job
  }

  const payload = args.md ? renderFlueMarkdown(map) : JSON.stringify(map, null, 2);

  if (args.out) {
    await writeFile(args.out, payload, 'utf8');
    console.error(`[delta-scp] wrote ${args.out}`);
  } else {
    process.stdout.write(payload + (payload.endsWith('\n') ? '' : '\n'));
  }
}

main().catch((err) => {
  console.error('[delta-scp] error:', err);
  process.exit(1);
});
