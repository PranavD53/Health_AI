import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/profile': 'http://127.0.0.1:8000',
      '/doctors': 'http://127.0.0.1:8000',
      '/dashboard-data': 'http://127.0.0.1:8000',
      '/emergency': 'http://127.0.0.1:8000',
      '/ai': 'http://127.0.0.1:8000',
      '/chats': 'http://127.0.0.1:8000',
      '/appointment/': 'http://127.0.0.1:8000',
      '/records/': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
      '/notifications': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/admin/': 'http://127.0.0.1:8000',
      '/doctor/': 'http://127.0.0.1:8000'
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
  }
})

