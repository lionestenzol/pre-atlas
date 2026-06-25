import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The UI calls /api/* and Vite proxies it to the live delta-scp gateway on :3012.
// This keeps the browser same-origin (no CORS) and lets the demo adapter stay
// a plain backend with no CORS knowledge.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:3012',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
});
