import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        // Las librerías (React, Mantine…) van en archivos aparte: cambian poco, así que el
        // navegador las guarda en caché y en cada actualización solo descarga nuestro código.
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/ },
            { name: 'mantine', test: /node_modules[\\/]@mantine[\\/]/ },
            { name: 'librerias', test: /node_modules[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    // Proxy de desarrollo: el navegador pide /api/... al propio Vite (mismo
    // origen, sin problemas de CORS) y Vite lo reenvía a la API FastAPI.
    //   /api/salud  ->  http://127.0.0.1:8000/salud
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
