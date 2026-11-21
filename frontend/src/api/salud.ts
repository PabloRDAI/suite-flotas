// Comprobación de /salud (pantalla "Estado del sistema"). Es pública: no usa token.

/** Lo que devuelve GET /salud (mismo formato que app/main.py del backend). */
export type RespuestaSalud = {
  estado: 'ok' | 'error'
  base_de_datos: string
}

/** Los tres resultados posibles al comprobar la salud del sistema. */
export type ResultadoSalud =
  | { tipo: 'ok'; datos: RespuestaSalud } // API y BD funcionando (HTTP 200)
  | { tipo: 'bd_caida'; datos: RespuestaSalud } // API viva, BD sin conexión (HTTP 503)
  | { tipo: 'api_caida'; mensaje: string } // la API no contesta

/** Llama a /salud y traduce la respuesta. Nunca lanza excepciones. */
export async function comprobarSalud(timeoutMs = 8000): Promise<ResultadoSalud> {
  try {
    const respuesta = await fetch('/api/salud', { signal: AbortSignal.timeout(timeoutMs) })
    if (respuesta.status === 200) {
      return { tipo: 'ok', datos: (await respuesta.json()) as RespuestaSalud }
    }
    if (respuesta.status === 503) {
      return { tipo: 'bd_caida', datos: (await respuesta.json()) as RespuestaSalud }
    }
    return {
      tipo: 'api_caida',
      mensaje: `La API no responde correctamente (HTTP ${respuesta.status}). ¿Está arrancado el backend?`,
    }
  } catch {
    return { tipo: 'api_caida', mensaje: 'No se puede contactar con la API. ¿Está arrancado el backend?' }
  }
}
