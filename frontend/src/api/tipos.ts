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

export type Puesto = 'conductor' | 'mecanico' | 'trafico' | 'otro'

export type Persona = {
  id: number
  nombre: string
  puesto: Puesto
  centro_id: number
  fecha_alta: string
  activo: boolean
  fecha_baja: string | null
  usuario_id: number | null
  semaforo: Semaforo // peor semáforo de su documentación vigente (PER-02)
}

export type Asignacion = {
  id: number
  persona_id: number
  persona_nombre: string
  vehiculo_id: number
  matricula: string
  desde: string
  hasta: string | null
  habitual: boolean
  notas: string | null
  vigente: boolean
  avisos: string[] // PER-04: documentación caducada del conductor (no bloquea)
}

export type VehiculoPanel = {
  id: number
  matricula: string
  marca: string
  modelo: string
  tipo_id: number
  centro_id: number
  km_actuales: number
  estado: EstadoVehiculo
  apto: boolean
  motivos: string[]
  semaforo: Semaforo
}

export type AlertaPanel = {
  tipo: 'vencimiento'
  semaforo: Semaforo
  vehiculo_id: number
  matricula: string
  mensaje: string
  fecha: string
  dias_restantes: number
}

export type Panel = {
  fecha: string
  contadores: {
    total: number
    operativo: number
    en_taller: number
    inmovilizado: number
    aptos: number
    no_aptos: number
  }
  vehiculos: VehiculoPanel[]
  alertas: AlertaPanel[]
}

export type Aptitud = {
  apto: boolean
  motivos: string[]
  semaforo: Semaforo
}
