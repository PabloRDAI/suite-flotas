// Formato de números y fechas en español.

const numero = new Intl.NumberFormat('es-ES')

/** 123456 -> "123.456 km" */
export const formatoKm = (km: number): string => `${numero.format(km)} km`

const euros = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })

/** 1234.5 -> "1.234,50 €" */
export const formatoEuros = (importe: number): string => euros.format(importe)

/** 1200 -> "1.200" */
export const formatoNumero = (n: number): string => numero.format(n)

/** "2026-11-21" -> "21/11/2026" (sin pasar por Date, para evitar desfases de zona horaria). */
export function formatoFecha(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${anio}`
}

/** Fecha de hoy en formato "AAAA-MM-DD" (hora local, para los campos de fecha). */
export function hoyIso(): string {
  const d = new Date()
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

/** "en_taller" -> "En taller" */
export function etiqueta(valor: string): string {
  const texto = valor.replaceAll('_', ' ')
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

export const nombresPuesto: Record<string, string> = {
  conductor: 'Conductor/a',
  mecanico: 'Mecánico/a',
  trafico: 'Tráfico',
  otro: 'Otro',
}

export const nombresRol: Record<string, string> = {
  admin: 'Gerente',
  trafico: 'Tráfico',
  taller: 'Taller',
  conductor: 'Conductor',
}

const porcentaje = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** 76.2 -> "76,2 %" */
export const formatoPorcentaje = (valor: number): string => `${porcentaje.format(valor)} %`

const eurosKm = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 3, maximumFractionDigits: 3 })

/** 0.045 -> "0,045 €/km" */
export const formatoEurosKm = (valor: number): string => `${eurosKm.format(valor)}/km`
