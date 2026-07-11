import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const mockApiPort = process.env.E2E_API_PORT || '8001'
  const apiTarget = mode === 'e2e'
    ? `http://127.0.0.1:${mockApiPort}`
    : 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    build: {
      // Keep every production chunk below the warning budget. These groups are
      // based on package boundaries so hashes remain stable across app-only
      // changes and the heavy UI/chart runtimes can be cached independently.
      // Element Plus is intentionally kept as one cacheable framework chunk.
      // 820 kB is the explicit ceiling; application and chart chunks remain
      // independently cached and substantially smaller.
      chunkSizeWarningLimit: 820,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            const moduleId = id.replaceAll('\\', '/')
            if (moduleId.includes('/element-plus/') || moduleId.includes('/@element-plus/')) return 'element-plus'
            if (moduleId.includes('/echarts/') || moduleId.includes('/zrender/')) return 'charts'
            if (moduleId.includes('/vue/') || moduleId.includes('/vue-router/')) return 'vue-vendor'
            if (moduleId.includes('/axios/')) return 'http-vendor'
            if (moduleId.includes('/marked/') || moduleId.includes('/dompurify/')) return 'content-vendor'
            return 'vendor'
          }
        }
      }
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          timeout: 300_000,
          proxyTimeout: 300_000
        }
      }
    }
  }
})
