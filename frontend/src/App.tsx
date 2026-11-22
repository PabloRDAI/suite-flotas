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
const Personal = lazy(() => import('./pantallas/Personal.tsx'))
const FichaPersona = lazy(() => import('./pantallas/FichaPersona.tsx'))
const Taller = lazy(() => import('./pantallas/Taller.tsx'))
const Averias = lazy(() => import('./pantallas/Averias.tsx'))
const ComunicarAveria = lazy(() => import('./pantallas/ComunicarAveria.tsx'))
const Inicio = lazy(() => import('./pantallas/Inicio.tsx'))
const OrdenTrabajo = lazy(() => import('./pantallas/OrdenTrabajo.tsx'))

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
          <Route path="/" element={<Inicio />} />
          <Route path="/panel" element={<Panel />} />
          <Route path="/vehiculos" element={<Vehiculos />} />
          <Route path="/vehiculos/:id" element={<FichaVehiculo />} />
          <Route path="/personal" element={<Personal />} />
          <Route path="/personal/:id" element={<FichaPersona />} />
          <Route path="/taller" element={<Taller />} />
          <Route path="/ordenes-trabajo/:id" element={<OrdenTrabajo />} />
          <Route path="/averias" element={<Averias />} />
          <Route path="/averias/nueva" element={<ComunicarAveria />} />
          <Route path="/sistema" element={<EstadoSistema />} />
        </Route>

        {/* Cualquier otra URL lleva al inicio de cada rol (o al login si no hay sesión). */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
