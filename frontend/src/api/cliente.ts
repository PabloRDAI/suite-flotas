// Cliente HTTP de la API: añade el token de sesión, traduce errores y avisa si la sesión caduca.
// Todas las rutas empiezan por /api; en desarrollo Vite las reenvía a FastAPI (vite.config.ts).

const CLAVE_TOKEN = 'suite-flotas.token'

export const tokenGuardado = (): string | null => localStorage.getItem(CLAVE_TOKEN)
export const guardarToken = (token: string): void => localStorage.setItem(CLAVE_TOKEN, token)
export const borrarToken = (): void => localStorage.removeItem(CLAVE_TOKEN)

/** Error de la API con su código HTTP y el mensaje ("detail") que envía el backend. */
export class ErrorApi extends Error {
  readonly status: number
  /** El "detail" tal cual, para errores con datos (p. ej. la lista de filas de una importación). */
  readonly detalle: unknown

  constructor(status: number, mensaje: string, detalle?: unknown) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.status = status
    this.detalle = detalle
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
  // Errores con datos (importación): { mensaje, errores: [...] }.
  const mensaje = (detalle as { mensaje?: unknown } | null)?.mensaje
  if (typeof mensaje === 'string') return mensaje
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
export async function api<T>(
  ruta: string,
  opciones: { metodo?: string; cuerpo?: unknown; formulario?: FormData } = {},
): Promise<T> {
  const token = tokenGuardado()
  const respuesta = await fetch(`/api${ruta}`, {
    method: opciones.metodo ?? 'GET',
    headers: {
      // Con FormData (archivos) NO se pone Content-Type: el navegador añade el
      // "multipart/form-data; boundary=…" correcto él solo.
      ...(opciones.cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opciones.formulario ?? (opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined),
    // Toda petición de red con límite de espera (más amplio si se sube un archivo).
    signal: AbortSignal.timeout(opciones.formulario ? 60_000 : 15_000),
  })

  if (respuesta.status === 204) return undefined as T // sin contenido (p. ej. tras un DELETE)

  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    if (respuesta.status === 401 && token) alCaducarSesion()
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status), (cuerpo as { detail?: unknown } | null)?.detail)
  }
  return cuerpo as T
}

/**
 * Descarga un archivo protegido (p. ej. la foto de una avería) con el token de sesión.
 * Un <img src="…"> no puede enviar la cabecera Authorization, así que se descarga
 * aquí y se muestra con una URL local (URL.createObjectURL).
 */
export async function descargar(ruta: string): Promise<Blob> {
  const token = tokenGuardado()
  const respuesta = await fetch(`/api${ruta}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(30_000),
  })
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, 'No se ha podido descargar el archivo')
  return respuesta.blob()
}

/** Descarga un archivo de la API y lo guarda en el equipo (p. ej. un Excel exportado, GEN-06).
 *  El nombre lo decide el servidor (cabecera Content-Disposition); si no viene, se usa `porDefecto`. */
export async function guardarArchivo(ruta: string, porDefecto: string): Promise<void> {
  const token = tokenGuardado()
  const respuesta = await fetch(`/api${ruta}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(60_000),
  })
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, 'No se ha podido descargar el archivo')
  const nombre = /filename="([^"]+)"/.exec(respuesta.headers.get('Content-Disposition') ?? '')?.[1] ?? porDefecto
  const url = URL.createObjectURL(await respuesta.blob())
  // Un enlace temporal con "download": el navegador guarda el archivo en vez de abrirlo.
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  enlace.click()
  URL.revokeObjectURL(url)
}
