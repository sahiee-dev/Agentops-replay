import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  optimizeDeps: {
    force: true,  // Force re-optimization
    include: ['react', 'react-dom', 'axios', 'react-router-dom'],
    exclude: []
  },
  cacheDir: '.vite-cache'  // Use custom cache directory
})
