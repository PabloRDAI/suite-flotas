// Comunicación con la API del backend.
// Todas las rutas empiezan por /api: en desarrollo, Vite las reenvía a FastAPI
// (ver el proxy en vite.config.ts).

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

/**
 * Llama a /salud y traduce la respuesta HTTP a un ResultadoSalud.
 * Nunca lanza excepciones: cualquier fallo se devuelve como 'api_caida'.
 */
export async function comprobarSalud(timeoutMs = 8000): Promise<ResultadoSalud> {
  try {
    // AbortSignal.timeout: si en timeoutMs no hay respuesta, se cancela la petición
    // (toda operación de red necesita un límite de espera).
    const respuesta = await fetch('/api/salud', { signal: AbortSignal.timeout(timeoutMs) })

    if (respuesta.status === 200) {
      return { tipo: 'ok', datos: (await respuesta.json()) as RespuestaSalud }
    }
    if (respuesta.status === 503) {
      return { tipo: 'bd_caida', datos: (await respuesta.json()) as RespuestaSalud }
    }
    // Otro código (p. ej. 500 del proxy de Vite cuando uvicorn no está arrancado).
    return {
      tipo: 'api_caida',
      mensaje: `La API no responde correctamente (HTTP ${respuesta.status}). ¿Está arrancado el backend?`,
    }
  } catch {
    return { tipo: 'api_caida', mensaje: 'No se puede contactar con la API. ¿Está arrancado el backend?' }
  }
}
