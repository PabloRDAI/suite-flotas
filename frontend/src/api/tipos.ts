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
  tipo: 'vencimiento' | 'preventivo' | 'averia' // documentación (FLO-06), preventivo (MAN-02) o avería (MAN-03)
  semaforo: Semaforo
  vehiculo_id: number
  matricula: string
  mensaje: string
  fecha: string | null // un preventivo solo por km no tiene fecha
  dias_restantes: number | null
}

// --- Averías (MAN-03) ---

export type Gravedad = 'leve' | 'grave' | 'inmoviliza'
export type EstadoAveria = 'comunicada' | 'en_reparacion' | 'resuelta'

export type Averia = {
  id: number
  vehiculo_id: number
  matricula: string
  comunicada_por: string | null
  comunicada_en: string // fecha y hora ISO
  descripcion: string
  gravedad: Gravedad
  estado: EstadoAveria
  tiene_foto: boolean
  resuelta_en: string | null
  nota_resolucion: string | null
  estado_vehiculo: EstadoVehiculo // tras la avería: "al instante" (MAN-03)
}

export type VehiculoSugerido = {
  id: number
  matricula: string
  marca: string
  modelo: string
  habitual: boolean
}

// --- Mantenimiento preventivo (MAN-01, MAN-02) ---

export type SituacionPreventivo = 'al_dia' | 'proximo' | 'vencido'

export type Preventivo = {
  plan_id: number
  plan_nombre: string
  intervalo_km: number | null
  intervalo_dias: number | null
  tareas: string[]
  ultima_fecha: string
  ultimos_km: number
  proxima_fecha: string | null
  proximos_km: number | null
  situacion: SituacionPreventivo
  motivo: string
  dias_restantes: number | null
  km_restantes: number | null
}

export type PrevisionItem = {
  vehiculo_id: number
  matricula: string
  tipo_id: number
  centro_id: number
  km_actuales: number
  plan_id: number
  plan_nombre: string
  tareas: string[]
  situacion: SituacionPreventivo
  motivo: string
  proxima_fecha: string | null
  proximos_km: number | null
  dias_restantes: number | null
  km_restantes: number | null
  urgencia: number
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
