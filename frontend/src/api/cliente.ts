// Cliente HTTP de la API: añade el token de sesión, traduce errores y avisa si la sesión caduca.
// Todas las rutas empiezan por /api; en desarrollo Vite las reenvía a FastAPI (vite.config.ts).

const CLAVE_TOKEN = 'suite-flotas.token'

export const tokenGuardado = (): string | null => localStorage.getItem(CLAVE_TOKEN)
export const guardarToken = (token: string): void => localStorage.setItem(CLAVE_TOKEN, token)
export const borrarToken = (): void => localStorage.removeItem(CLAVE_TOKEN)

/** Error de la API con su código HTTP y el mensaje ("detail") que envía el backend. */
export class ErrorApi extends Error {
  readonly status: number

  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.status = status
  }
}

// Función que se llama cuando la API responde 401 a una petición con token
// (token caducado o usuario desactivado). La registra el proveedor de sesión.
let alCaducarSesion: () => void = () => {}
export const registrarAlCaducarSesion = (funcion: () => void): void => {
  alCaducarSesion = funcion
}

/** Extrae un mensaje legible del cuerpo de error de FastAPI. */
function mensajeDeError(cuerpo: unknown, status: number): string {
  const detalle = (cuerpo as { detail?: unknown } | null)?.detail
  if (typeof detalle === 'string') return detalle
  // 422 de validación de Pydantic: lista de errores por campo.
  if (Array.isArray(detalle) && detalle.length > 0) {
    return detalle.map((e: { msg?: string }) => e.msg ?? 'Dato no válido').join('. ')
  }
  return `Error inesperado (HTTP ${status})`
}

/**
 * Hace una petición a la API y devuelve el JSON ya tipado.
 * Lanza ErrorApi si la respuesta no es correcta (4xx o 5xx).
 */
export async function api<T>(ruta: string, opciones: { metodo?: string; cuerpo?: unknown } = {}): Promise<T> {
  const token = tokenGuardado()
  const respuesta = await fetch(`/api${ruta}`, {
    method: opciones.metodo ?? 'GET',
    headers: {
      ...(opciones.cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined,
    signal: AbortSignal.timeout(15_000), // toda petición de red con límite de espera
  })

  if (respuesta.status === 204) return undefined as T // sin contenido (p. ej. tras un DELETE)

  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    if (respuesta.status === 401 && token) alCaducarSesion()
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status))
  }
  return cuerpo as T
}
