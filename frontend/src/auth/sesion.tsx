// Sesión del usuario: token, datos del usuario conectado, login y logout.
//
// - El token se guarda en localStorage para no perder la sesión al recargar la página.
// - El usuario se pide a GET /auth/yo con ese token.
// - Si la API responde 401 (token caducado o usuario desactivado), se cierra la sesión.

import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, borrarToken, guardarToken, registrarAlCaducarSesion, tokenGuardado } from '../api/cliente.ts'
import { useYo } from '../api/consultas.ts'
import { ContextoSesion, useSesion, type Sesion } from './contexto.ts'

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const cliente = useQueryClient()
  const [token, setToken] = useState<string | null>(tokenGuardado)
  const yo = useYo(token !== null)

  const salir = useCallback(() => {
    borrarToken()
    setToken(null)
    cliente.clear() // borra de la caché los datos del usuario anterior
  }, [cliente])

  // Si la API dice 401 con nuestro token, la sesión ya no vale.
  useEffect(() => registrarAlCaducarSesion(salir), [salir])

  const entrar = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api<{ access_token: string }>('/auth/login', {
        metodo: 'POST',
        cuerpo: { email, password },
      })
      cliente.clear()
      guardarToken(access_token)
      setToken(access_token)
    },
    [cliente],
  )

  const valor = useMemo<Sesion>(
    () => ({
      usuario: token ? (yo.data ?? null) : null,
      cargando: token !== null && yo.isPending,
      entrar,
      salir,
    }),
    [token, yo.data, yo.isPending, entrar, salir],
  )

  return <ContextoSesion value={valor}>{children}</ContextoSesion>
}

/** Protege una pantalla: sin sesión, redirige al login (y vuelve aquí después). */
export function RequiereSesion({ children }: { children: ReactNode }) {
  const { usuario, cargando } = useSesion()
  const ubicacion = useLocation()
  if (cargando) return null
  if (!usuario) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  return children
}
