// Contexto de la sesión y el hook para leerla. Va separado de los componentes
// (sesion.tsx) para que la recarga instantánea de Vite (Fast Refresh) funcione bien:
// un archivo de componentes solo debe exportar componentes.

import { createContext, use } from 'react'
import type { Usuario } from '../api/tipos.ts'

export type Sesion = {
  usuario: Usuario | null
  cargando: boolean
  entrar: (email: string, password: string) => Promise<void>
  salir: () => void
}

export const ContextoSesion = createContext<Sesion | null>(null)

/** Acceso a la sesión desde cualquier componente. */
export function useSesion(): Sesion {
  const sesion = use(ContextoSesion)
  if (!sesion) throw new Error('useSesion debe usarse dentro de <ProveedorSesion>')
  return sesion
}
