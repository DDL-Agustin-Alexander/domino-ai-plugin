import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Domino-compatible Vite configuration.
// Domino serves the App under a URL prefix and strips it before forwarding to the container.

export default defineConfig({
  plugins: [react()],

  // Required: relative asset URLs in the production build. The default '/' emits /assets/...
  // which 404s behind the proxy. (Vite ignores a relative base in the dev server.)
  base: './',

  // Local development on a laptop only (`npm run dev`). Inside Domino, test with App Preview,
  // which runs app.sh (build + server.js) in a real App runtime; the published App never uses
  // the Vite dev server or `vite preview`.
  server: {
    host: '0.0.0.0',
    port: 8888,
    strictPort: true,
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
