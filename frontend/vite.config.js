import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// esbuild's system temp removal is blocked on this Windows host; keep its
// temporary files inside the project so `npm run build` is reproducible.
const localTemp = resolve(fileURLToPath(new URL('.', import.meta.url)), '.tmp')
mkdirSync(localTemp, { recursive: true })
process.env.TEMP = localTemp
process.env.TMP = localTemp

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: { '/api': 'http://127.0.0.1:8501' },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
