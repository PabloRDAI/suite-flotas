// Página de inicio según el rol: cada uno empieza donde más lo necesita.
// - Conductor: comunicar una avería (su tarea principal; historia de usuario de MAN-03).
// - Resto: el panel de flota.

import { Navigate } from 'react-router'
import { useSesion } from '../auth/contexto.ts'

export default function Inicio() {
  const { usuario } = useSesion()
  return <Navigate to={usuario?.rol === 'conductor' ? '/averias/nueva' : '/panel'} replace />
}
