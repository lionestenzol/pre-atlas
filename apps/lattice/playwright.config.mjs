import { defineConfig, devices } from '@playwright/test';

// Serves apps/lattice on :3011 (reuses the running launch.json/preview server if
// already up) and runs the hermetic smoke in headless Chromium. The smoke
// intercepts the delta-kernel :3001 calls with a fixture, so it needs NO live
// backend — it guards the frontend graph data-flow only.
export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.mjs/,
  timeout: 30000,
  expect: { timeout: 8000 },
  use: { baseURL: 'http://127.0.0.1:3011', headless: true },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npx --yes http-server . -p 3011 -c-1 --silent',
    url: 'http://127.0.0.1:3011/index.html',
    reuseExistingServer: true,
    timeout: 30000,
  },
});
