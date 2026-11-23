import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import basicSsl from '@vitejs/plugin-basic-ssl'

const rootDir = path.dirname(fileURLToPath(import.meta.url))
const apiTarget = process.env.ANIROUTE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig(({ mode }) => ({
  // LAN mode is served over https (self-signed): phones only allow the camera and GPS on secure pages.
  plugins: [vue(), tailwindcss(), ...(mode === 'lan' ? [basicSsl({ name: 'aniroute-lan' })] : [])],
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
  // LAN mode (npm run lan): a phone on the same Wi-Fi opens this server, and every API call goes to the
  // same address and is forwarded to the backend below, so the phone never needs the backend's port.
  define: mode === 'lan' ? { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') } : {},
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/reports': { target: apiTarget, changeOrigin: true },
      '/samples': { target: apiTarget, changeOrigin: true },
    },
  },
  // MapLibre's worker is an ES module (it imports a shared chunk), so bundle workers as ES modules.
  worker: { format: 'es' },
  resolve: {
    alias: {
      '@': path.resolve(rootDir, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    restoreMocks: true,
  },
}))
