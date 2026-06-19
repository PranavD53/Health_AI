import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/profile': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/doctors': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/dashboard-data': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/emergency': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ai': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/chats': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/appointment': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/records/': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/notifications': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/audit': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin/dashboard': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin/verify-doctor': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin/complaints': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/doctor/dashboard': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true, changeOrigin: true },
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
  }
})

