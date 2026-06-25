/* global process */
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'
  const port = Number(env.VITE_PORT) || 5173

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
    preview: {
      host: '0.0.0.0',
      port,
    },
  }
})
