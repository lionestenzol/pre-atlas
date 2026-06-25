// Delta SCP · combined entrypoint — runs the API gateway and the worker loop
// in one process. `npm start`.

import { loadConfig, requireSupabase } from './config.js';
import { getSupabase } from './supabase.js';
import { startServer } from './server.js';
import { runWorker } from './worker.js';

function main() {
  const config = loadConfig();
  requireSupabase(config);
  const db = getSupabase(config);

  startServer();
  runWorker(db, config).catch((err) => {
    console.error('[delta-scp] worker crashed:', err);
    process.exit(1);
  });
}

main();
