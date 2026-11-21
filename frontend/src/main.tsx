// Punto de entrada: monta los "proveedores" que dan servicio a toda la aplicación.
//
//   MantineProvider      → aspecto y componentes (claro/oscuro según el sistema)
//   QueryClientProvider  → caché de datos de la API (TanStack Query)
//   BrowserRouter        → navegación entre pantallas por URL
//   ProveedorSesion      → usuario conectado y token

import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import './index.css'

import { MantineProvider, createTheme } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { ErrorApi } from './api/cliente.ts'
import App from './App.tsx'
import { ProveedorSesion } from './auth/sesion.tsx'

const tema = createTheme({
  primaryColor: 'indigo',
  fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
})

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      // Reintentar tiene sentido ante fallos de red, no ante un 4xx (403, 404, 422…): no cambiaría.
      retry: (intentos, error) => !(error instanceof ErrorApi && error.status < 500) && intentos < 2,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={tema} defaultColorScheme="auto">
      <Notifications position="top-right" />
      <QueryClientProvider client={clienteConsultas}>
        <BrowserRouter>
          <ProveedorSesion>
            <App />
          </ProveedorSesion>
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
)
