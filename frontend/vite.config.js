import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In dev the frontend calls /api and Vite forwards it to the backend: no CORS, same URL as production.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    // Plotly (~4.5 MB) is loaded with a dynamic import only when a graph is shown,
    // so its chunk size does not affect the initial load.
    chunkSizeWarningLimit: 5000,
  },
})
