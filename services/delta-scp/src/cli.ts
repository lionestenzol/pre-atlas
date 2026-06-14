// Delta SCP · standalone CLI — compress a repo without a queue or Supabase.
//
//   npm run compress -- <repo-url-or-local-path> [out.json]
//
// Useful for trying the DELTA SCP protocol offline. Prints the compressed
// symbolic map to stdout (or writes it to the given file).

import { writeFile } from 'node:fs/promises';
import { loadConfig } from './config.js';
import { compressRepository } from './source.js';

async function main() {
  const target = process.argv[2];
  const outPath = process.argv[3];
  if (!target) {
    console.error('usage: npm run compress -- <repo-url-or-local-path> [out.json]');
    process.exit(2);
  }

  const compressed = await compressRepository(target, loadConfig());
  const json = JSON.stringify(compressed, null, 2);

  if (outPath) {
    await writeFile(outPath, json, 'utf8');
    const { stats } = compressed;
    console.error(
      `[delta-scp] wrote ${outPath} · ${stats.files_included} files · ` +
        `raw≈${stats.raw_tokens_est} tok → compressed≈${stats.compressed_tokens_est} tok ` +
        `(yield ${stats.token_yield}, ratio ${stats.compression_ratio})`,
    );
  } else {
    process.stdout.write(json + '\n');
  }
}

main().catch((err) => {
  console.error('[delta-scp] error:', err);
  process.exit(1);
});
