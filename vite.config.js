import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Lokale Entwicklung: /api-Aufrufe an das FastAPI-Backend (Port 8000) weiterleiten.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
