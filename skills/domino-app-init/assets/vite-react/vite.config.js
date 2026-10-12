import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Domino-compatible Vite configuration.
// Domino serves the App under a URL prefix and strips it before forwarding to the container.

export default defineConfig({
  plugins: [react()],

  // Required: relative asset URLs. The default '/' emits /assets/... which 404s behind the proxy.
  base: './',

  // Used by `vite` (dev server) and `vite preview` only; the published App is served by server.js.
  // Domino Apps must listen on 0.0.0.0:8888. Inside a workspace that port belongs to the IDE,
  // so run the dev server with `npm run dev -- --port 8890` and open it through /proxy/8890/.
  server: {
    host: '0.0.0.0',
    port: 8888,
    strictPort: true,
  },

  preview: {
    host: '0.0.0.0',
    port: 8888,
    strictPort: true,
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
