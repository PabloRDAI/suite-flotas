// Consultas y operaciones de la API con TanStack Query.
//
// useQuery:    pide datos y devuelve { data, isPending, error }. Guarda la respuesta
//              en caché con su "queryKey": si otra pantalla pide lo mismo, no repite la petición.
// useMutation: envía cambios (POST, PATCH, DELETE). Al terminar, se "invalidan" las
//              consultas afectadas para que se vuelvan a pedir con los datos nuevos.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, descargar } from './cliente.ts'
import type {
  Aptitud,
  Asignacion,
  Averia,
  Centro,
  Gravedad,
  Historial,
  LecturaKm,
  OrdenTrabajo,
  Concepto,
  TipoOT,
  Indicadores,
  Panel,
  Persona,
  PrevisionItem,
  Preventivo,
  Recambio,
  TipoVehiculo,
  Usuario,
  Vehiculo,
  VehiculoSugerido,
  Vencimiento,
} from './tipos.ts'

// Claves de caché en un solo sitio, para no equivocarse al invalidarlas.
export const claves = {
  yo: ['yo'] as const,
  centros: ['centros'] as const,
  tiposVehiculo: ['tipos-vehiculo'] as const,
  vehiculos: (incluirBajas: boolean) => ['vehiculos', { incluirBajas }] as const,
  vehiculo: (id: number) => ['vehiculo', id] as const,
  km: (id: number) => ['vehiculo', id, 'km'] as const,
  vencimientos: (id: number) => ['vehiculo', id, 'vencimientos'] as const,
  aptitud: (id: number) => ['vehiculo', id, 'aptitud'] as const,
  panel: (centroId: string | null, tipoId: string | null) => ['panel', { centroId, tipoId }] as const,
  // Empieza por 'panel': al invalidar ['panel'] (cerrar una OT, una avería…) también se refrescan.
  indicadores: (centroId: string | null, tipoId: string | null) => ['panel', 'indicadores', { centroId, tipoId }] as const,
  asignacionesVehiculo: (id: number) => ['vehiculo', id, 'asignaciones'] as const,
  personas: (incluirBajas: boolean) => ['personas', { incluirBajas }] as const,
  persona: (id: number) => ['persona', id] as const,
  vencimientosPersona: (id: number) => ['persona', id, 'vencimientos'] as const,
  asignacionesPersona: (id: number) => ['persona', id, 'asignaciones'] as const,
  preventivos: (id: number) => ['vehiculo', id, 'preventivos'] as const,
  prevision: (centroId: string | null, tipoId: string | null) => ['prevision', { centroId, tipoId }] as const,
}

// --- Personal (PER-01, PER-02) -----------------------------------------------

export const usePersonas = (incluirBajas: boolean) =>
  useQuery({
    queryKey: claves.personas(incluirBajas),
    queryFn: () => api<Persona[]>(`/personas${incluirBajas ? '?incluir_bajas=true' : ''}`),
  })

export const usePersona = (id: number) =>
  useQuery({ queryKey: claves.persona(id), queryFn: () => api<Persona>(`/personas/${id}`) })

export const useVencimientosPersona = (id: number) =>
  useQuery({ queryKey: claves.vencimientosPersona(id), queryFn: () => api<Vencimiento[]>(`/personas/${id}/vencimientos`) })

// --- Asignaciones (PER-03, PER-04) -------------------------------------------

export const useAsignacionesVehiculo = (id: number) =>
  useQuery({
    queryKey: claves.asignacionesVehiculo(id),
    queryFn: () => api<Asignacion[]>(`/vehiculos/${id}/asignaciones`),
  })

export const useAsignacionesPersona = (id: number) =>
  useQuery({
    queryKey: claves.asignacionesPersona(id),
    queryFn: () => api<Asignacion[]>(`/personas/${id}/asignaciones`),
  })

/** Tras cualquier cambio en asignaciones, se refrescan las del vehículo y las de las personas. */
function useRefrescarAsignaciones() {
  const cliente = useQueryClient()
  return () => {
    void cliente.invalidateQueries({ queryKey: ['vehiculo'] })
    void cliente.invalidateQueries({ queryKey: ['persona'] })
  }
}

export type NuevaAsignacion = {
  persona_id: number
  vehiculo_id: number
  desde?: string
  hasta?: string
  habitual: boolean
  /** Si se indica, primero se finaliza esa asignación (cambio de conductor habitual en un paso). */
  finalizarAntes?: number
}

/** Asignar un conductor (PER-03). Devuelve la asignación con sus avisos (PER-04). */
export function useAsignar() {
  const refrescar = useRefrescarAsignaciones()
  return useMutation({
    mutationFn: async ({ finalizarAntes, ...datos }: NuevaAsignacion) => {
      if (finalizarAntes !== undefined) {
        await api<Asignacion>(`/asignaciones/${finalizarAntes}/finalizar`, { metodo: 'POST', cuerpo: {} })
      }
      return api<Asignacion>('/asignaciones', { metodo: 'POST', cuerpo: datos })
    },
    // onSettled (y no onSuccess): si se finalizó la anterior pero falló la nueva, hay que refrescar igual.
    onSettled: refrescar,
  })
}

/** Finalizar una asignación (por defecto termina ayer). */
export function useFinalizarAsignacion() {
  const refrescar = useRefrescarAsignaciones()
  return useMutation({
    mutationFn: (id: number) => api<Asignacion>(`/asignaciones/${id}/finalizar`, { metodo: 'POST', cuerpo: {} }),
    onSuccess: refrescar,
  })
}

/** Panel de flota (FLO-04): todo calculado en el servidor en una sola petición. */
export const usePanel = (centroId: string | null, tipoId: string | null) =>
  useQuery({
    queryKey: claves.panel(centroId, tipoId),
    queryFn: () => {
      const filtros = new URLSearchParams()
      if (centroId) filtros.set('centro_id', centroId)
      if (tipoId) filtros.set('tipo_id', tipoId)
      return api<Panel>(`/panel${filtros.size ? `?${filtros}` : ''}`)
    },
    placeholderData: (anterior) => anterior, // al cambiar de filtro, mantiene los datos previos mientras carga
  })

/** Indicadores de mantenimiento (MAN-08) de los últimos 6 meses, con los mismos filtros que el panel. */
export const useIndicadores = (centroId: string | null, tipoId: string | null) =>
  useQuery({
    queryKey: claves.indicadores(centroId, tipoId),
    queryFn: () => {
      const filtros = new URLSearchParams()
      if (centroId) filtros.set('centro_id', centroId)
      if (tipoId) filtros.set('tipo_id', tipoId)
      return api<Indicadores>(`/panel/indicadores${filtros.size ? `?${filtros}` : ''}`)
    },
    placeholderData: (anterior) => anterior,
  })

export const useYo = (activa: boolean) =>
  useQuery({ queryKey: claves.yo, queryFn: () => api<Usuario>('/auth/yo'), enabled: activa })

// Los catálogos cambian poco: se consideran "frescos" durante 5 minutos.
export const useCentros = () =>
  useQuery({ queryKey: claves.centros, queryFn: () => api<Centro[]>('/centros'), staleTime: 5 * 60_000 })

export const useTiposVehiculo = () =>
  useQuery({
    queryKey: claves.tiposVehiculo,
    queryFn: () => api<TipoVehiculo[]>('/tipos-vehiculo'),
    staleTime: 5 * 60_000,
  })

export const useVehiculos = (incluirBajas: boolean) =>
  useQuery({
    queryKey: claves.vehiculos(incluirBajas),
    queryFn: () => api<Vehiculo[]>(`/vehiculos${incluirBajas ? '?incluir_bajas=true' : ''}`),
  })

export const useVehiculo = (id: number) =>
  useQuery({ queryKey: claves.vehiculo(id), queryFn: () => api<Vehiculo>(`/vehiculos/${id}`) })

export const useLecturasKm = (id: number) =>
  useQuery({ queryKey: claves.km(id), queryFn: () => api<LecturaKm[]>(`/vehiculos/${id}/km`) })

export const useVencimientos = (id: number) =>
  useQuery({ queryKey: claves.vencimientos(id), queryFn: () => api<Vencimiento[]>(`/vehiculos/${id}/vencimientos`) })

export const useAptitud = (id: number) =>
  useQuery({ queryKey: claves.aptitud(id), queryFn: () => api<Aptitud>(`/vehiculos/${id}/aptitud`) })

/** Registrar una lectura de km (FLO-05). Al terminar, refresca la ficha, el historial y el listado. */
export function useRegistrarLectura(vehiculoId: number) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: (datos: { km: number; fecha?: string }) =>
      api<LecturaKm>(`/vehiculos/${vehiculoId}/km`, { metodo: 'POST', cuerpo: datos }),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ['vehiculo', vehiculoId] }) // ficha, km, aptitud…
      void cliente.invalidateQueries({ queryKey: ['vehiculos'] }) // los km del listado
      void cliente.invalidateQueries({ queryKey: ['panel'] }) // y los del panel
    },
  })
}

// --- Mantenimiento preventivo (MAN-01, MAN-02) -------------------------------

export const usePreventivos = (vehiculoId: number) =>
  useQuery({
    queryKey: claves.preventivos(vehiculoId),
    queryFn: () => api<Preventivo[]>(`/vehiculos/${vehiculoId}/preventivos`),
  })

/** Previsión (MAN-02): vencidos y lo que toca en 30 días o 2.000 km, ya ordenado por urgencia. */
export const usePrevision = (centroId: string | null, tipoId: string | null) =>
  useQuery({
    queryKey: claves.prevision(centroId, tipoId),
    queryFn: () => {
      const filtros = new URLSearchParams()
      if (centroId) filtros.set('centro_id', centroId)
      if (tipoId) filtros.set('tipo_id', tipoId)
      return api<PrevisionItem[]>(`/preventivos/prevision${filtros.size ? `?${filtros}` : ''}`)
    },
    placeholderData: (anterior) => anterior,
  })

/** Registrar que se hizo un preventivo (sin datos: hoy y con los km actuales). */
export function useRegistrarRealizacion() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ vehiculoId, planId }: { vehiculoId: number; planId: number }) =>
      api<Preventivo[]>(`/vehiculos/${vehiculoId}/preventivos/${planId}/realizado`, { metodo: 'POST', cuerpo: {} }),
    onSuccess: (_datos, { vehiculoId }) => {
      void cliente.invalidateQueries({ queryKey: claves.preventivos(vehiculoId) })
      void cliente.invalidateQueries({ queryKey: ['prevision'] })
      void cliente.invalidateQueries({ queryKey: ['panel'] })
    },
  })
}

// --- Averías (MAN-03) --------------------------------------------------------

export const useAverias = (abiertas: boolean, gravedad: string | null = null) =>
  useQuery({
    queryKey: ['averias', { abiertas, gravedad }],
    queryFn: () => {
      const filtros = new URLSearchParams({ abiertas: String(abiertas) })
      if (gravedad) filtros.set('gravedad', gravedad)
      return api<Averia[]>(`/averias?${filtros}`)
    },
  })

/** Vehículos asignados al usuario: para preseleccionar al comunicar una avería. */
export const useVehiculosSugeridos = () =>
  useQuery({ queryKey: ['averias', 'sugeridos'], queryFn: () => api<VehiculoSugerido[]>('/averias/vehiculos-sugeridos') })

/** Foto de una avería como URL local (se descarga con el token; ver descargar() en cliente.ts). */
export const useFotoAveria = (averiaId: number, activa: boolean) =>
  useQuery({
    queryKey: ['averias', averiaId, 'foto'],
    queryFn: async () => URL.createObjectURL(await descargar(`/averias/${averiaId}/foto`)),
    enabled: activa,
    staleTime: Infinity, // una foto no cambia
  })

/** Al comunicar o resolver una avería cambian el estado del vehículo, el panel y las listas. */
function useRefrescarTrasAveria() {
  const cliente = useQueryClient()
  return () => {
    for (const clave of [['averias'], ['vehiculo'], ['vehiculos'], ['panel']]) {
      void cliente.invalidateQueries({ queryKey: clave })
    }
  }
}

export type NuevaAveria = { vehiculoId: number; descripcion: string; gravedad: Gravedad; foto: File | null }

export function useComunicarAveria() {
  const refrescar = useRefrescarTrasAveria()
  return useMutation({
    mutationFn: ({ vehiculoId, descripcion, gravedad, foto }: NuevaAveria) => {
      // Formulario multipart (por la foto), no JSON.
      const formulario = new FormData()
      formulario.set('vehiculo_id', String(vehiculoId))
      formulario.set('descripcion', descripcion)
      formulario.set('gravedad', gravedad)
      if (foto) formulario.set('foto', foto)
      return api<Averia>('/averias', { metodo: 'POST', formulario })
    },
    onSuccess: refrescar,
  })
}

export function useResolverAveria() {
  const refrescar = useRefrescarTrasAveria()
  return useMutation({
    mutationFn: ({ id, nota }: { id: number; nota: string }) =>
      api<Averia>(`/averias/${id}/resolver`, { metodo: 'POST', cuerpo: { nota: nota || null } }),
    onSuccess: refrescar,
  })
}

// --- Órdenes de trabajo (MAN-04 a MAN-07) ------------------------------------

export type FiltrosOT = { abiertas?: boolean; estado?: string; vehiculoId?: number; cerradasDesde?: string }

export const useOrdenes = (filtros: FiltrosOT) =>
  useQuery({
    queryKey: ['ordenes', filtros],
    queryFn: () => {
      const p = new URLSearchParams()
      if (filtros.abiertas) p.set('abiertas', 'true')
      if (filtros.estado) p.set('estado', filtros.estado)
      if (filtros.vehiculoId) p.set('vehiculo_id', String(filtros.vehiculoId))
      if (filtros.cerradasDesde) p.set('cerradas_desde', filtros.cerradasDesde)
      return api<OrdenTrabajo[]>(`/ordenes-trabajo${p.size ? `?${p}` : ''}`)
    },
  })

export const useOrden = (id: number) =>
  useQuery({ queryKey: ['orden', id], queryFn: () => api<OrdenTrabajo>(`/ordenes-trabajo/${id}`) })

/** MAN-07: historial de mantenimiento del vehículo con su resumen de costes. */
export const useHistorial = (vehiculoId: number) =>
  useQuery({ queryKey: ['vehiculo', vehiculoId, 'historial'], queryFn: () => api<Historial>(`/vehiculos/${vehiculoId}/historial`) })

/** Cualquier cambio en una OT afecta a: OT, vehículo (estado, km), panel, averías y preventivos. */
function useRefrescarTrasOT() {
  const cliente = useQueryClient()
  return () => {
    for (const clave of [['ordenes'], ['orden'], ['vehiculo'], ['vehiculos'], ['panel'], ['averias'], ['prevision']]) {
      void cliente.invalidateQueries({ queryKey: clave })
    }
  }
}

export type NuevaOT =
  | { averia_id: number }
  | { vehiculo_id: number; plan_id: number }
  | { vehiculo_id: number; tipo: TipoOT; descripcion: string; inmoviliza: boolean }

export function useCrearOT() {
  const refrescar = useRefrescarTrasOT()
  return useMutation({
    mutationFn: (datos: NuevaOT) => api<OrdenTrabajo>('/ordenes-trabajo', { metodo: 'POST', cuerpo: datos }),
    onSuccess: refrescar,
  })
}

export type AccionOT =
  | { accion: 'iniciar' }
  | { accion: 'cerrar'; km: number; fecha?: string; trabajo_realizado?: string }
  | { accion: 'cancelar'; motivo?: string }

/** Flujo de la OT (MAN-05): iniciar, cerrar (con km y fecha) o cancelar. */
export function useAccionOT(otId: number) {
  const refrescar = useRefrescarTrasOT()
  return useMutation({
    mutationFn: ({ accion, ...datos }: AccionOT) =>
      api<OrdenTrabajo>(`/ordenes-trabajo/${otId}/${accion}`, { metodo: 'POST', cuerpo: datos }),
    onSuccess: refrescar,
  })
}

export function useAnadirLinea(otId: number) {
  const refrescar = useRefrescarTrasOT()
  return useMutation({
    mutationFn: (linea: { concepto: Concepto; recambio_id?: number | null; descripcion: string; cantidad: number; precio_unitario: number }) =>
      api<OrdenTrabajo>(`/ordenes-trabajo/${otId}/lineas`, { metodo: 'POST', cuerpo: linea }),
    onSuccess: refrescar,
  })
}

export function useBorrarLinea(otId: number) {
  const refrescar = useRefrescarTrasOT()
  return useMutation({
    mutationFn: (lineaId: number) => api<void>(`/ordenes-trabajo/${otId}/lineas/${lineaId}`, { metodo: 'DELETE' }),
    onSuccess: refrescar,
  })
}

// --- Catálogo de recambios (MAN-09) ------------------------------------------

export const useRecambios = (incluirBajas = false) =>
  useQuery({
    queryKey: ['recambios', { incluirBajas }],
    queryFn: () => api<Recambio[]>(`/recambios${incluirBajas ? '?incluir_bajas=true' : ''}`),
  })

type DatosRecambio = { referencia: string; nombre: string; precio: number }

/** Alta (sin id) o edición (con id) de un recambio. */
export function useGuardarRecambio() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...datos }: DatosRecambio & { id?: number }) =>
      id === undefined
        ? api<Recambio>('/recambios', { metodo: 'POST', cuerpo: datos })
        : api<Recambio>(`/recambios/${id}`, { metodo: 'PATCH', cuerpo: datos }),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: ['recambios'] }),
  })
}

export function useBajaRecambio() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/recambios/${id}`, { metodo: 'DELETE' }),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: ['recambios'] }),
  })
}
