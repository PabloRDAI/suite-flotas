// Tipos TypeScript de lo que devuelve la API (mismos campos que backend/app/schemas.py).
// Si cambia un esquema del backend, hay que reflejarlo aquí.

export type Rol = 'admin' | 'trafico' | 'taller' | 'conductor'
export type EstadoVehiculo = 'operativo' | 'en_taller' | 'inmovilizado' | 'baja'
export type Semaforo = 'verde' | 'ambar' | 'rojo'

export type Usuario = {
  id: number
  email: string
  nombre: string
  rol: Rol
  empresa_id: number
}

export type Centro = {
  id: number
  nombre: string
  tipo: 'cochera' | 'taller' | 'oficina' | 'otro'
  direccion: string | null
  activo: boolean
}

export type TipoVehiculo = {
  id: number
  nombre: string
  unidad_capacidad: 'plazas' | 'kg'
  activo: boolean
}

export type Vehiculo = {
  id: number
  matricula: string
  marca: string
  modelo: string
  anio: number
  capacidad: number | null
  combustible: string
  km_actuales: number
  estado: EstadoVehiculo
  centro_id: number
  tipo_id: number
  activo: boolean
}

export type LecturaKm = {
  id: number
  vehiculo_id: number
  fecha: string // "AAAA-MM-DD"
  km: number
  registrada_por_id: number | null
}

export type Vencimiento = {
  id: number
  tipo_id: number
  tipo_nombre: string
  fecha_caducidad: string
  notas: string | null
  dias_restantes: number
  semaforo: Semaforo
  vigente: boolean
}

export type Aptitud = {
  apto: boolean
  motivos: string[]
  semaforo: Semaforo
}
