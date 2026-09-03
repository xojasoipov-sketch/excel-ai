import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The Electron desktop build opens index.html over file://, which only works with
// relative asset paths. The web build is served from the domain root and needs
// absolute ones — relative paths would break on client-side routes. BUILD_TARGET
// (set by the `desktop`/`dist:win` npm scripts) selects between them.
const isDesktopBuild = process.env.BUILD_TARGET === 'desktop'

// https://vitejs.dev/config/
export default defineConfig({
  base: isDesktopBuild ? './' : '/',
  plugins: [react()],
  server: {
    port: 5173,
  },
})
