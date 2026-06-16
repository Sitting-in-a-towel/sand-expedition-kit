import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// dev served at /, production build served under the pred.city backend.
// The path is intentionally non-obvious (owner request 2026-06-11) — must match the
// route in Predecessor website backend/server.js.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  server: { port: 3010 },
  base: command === 'build' ? '/sand-wormpit-7x2k/' : '/',
}))
