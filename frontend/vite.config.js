import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const apiTarget = mode === 'e2e'
    ? 'http://127.0.0.1:8001'
    : 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        '/api': apiTarget
      }
    }
  }
})
