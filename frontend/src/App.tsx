// Rutas de la aplicación: qué pantalla se muestra en cada URL.
//
// Las pantallas se cargan de forma DIFERIDA (lazy): el código de cada una se descarga
// la primera vez que se visita, no todo al abrir la aplicación. Mientras llega,
// <Suspense> muestra un indicador de carga.

import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { RequiereSesion } from './auth/sesion.tsx'
import { Cargando } from './componentes/Carga.tsx'
import Layout from './componentes/Layout.tsx'

const Login = lazy(() => import('./pantallas/Login.tsx'))
const Panel = lazy(() => import('./pantallas/Panel.tsx'))
const Vehiculos = lazy(() => import('./pantallas/Vehiculos.tsx'))
const FichaVehiculo = lazy(() => import('./pantallas/FichaVehiculo.tsx'))
const EstadoSistema = lazy(() => import('./pantallas/EstadoSistema.tsx'))

export default function App() {
  return (
    <Suspense fallback={<Cargando />}>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Todo lo de dentro exige sesión y comparte la estructura (cabecera + menú). */}
        <Route
          element={
            <RequiereSesion>
              <Layout />
            </RequiereSesion>
          }
        >
          <Route path="/panel" element={<Panel />} />
          <Route path="/vehiculos" element={<Vehiculos />} />
          <Route path="/vehiculos/:id" element={<FichaVehiculo />} />
          <Route path="/sistema" element={<EstadoSistema />} />
        </Route>

        {/* Cualquier otra URL lleva al panel (o al login si no hay sesión). */}
        <Route path="*" element={<Navigate to="/panel" replace />} />
      </Routes>
    </Suspense>
  )
}
