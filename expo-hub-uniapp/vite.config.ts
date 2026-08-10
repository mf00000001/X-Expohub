import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/auth': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/exhibitions': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/booths': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/products': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/procurements': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/messages': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/reviews': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
      '/dashboard': {
        target: 'http://localhost:8002',
        changeOrigin: true
      },
    }
  }
})
