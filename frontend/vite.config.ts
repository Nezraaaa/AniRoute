import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
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
})
