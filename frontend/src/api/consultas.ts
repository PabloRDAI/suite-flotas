// Consultas y operaciones de la API con TanStack Query.
//
// useQuery:    pide datos y devuelve { data, isPending, error }. Guarda la respuesta
//              en caché con su "queryKey": si otra pantalla pide lo mismo, no repite la petición.
// useMutation: envía cambios (POST, PATCH, DELETE). Al terminar, se "invalidan" las
//              consultas afectadas para que se vuelvan a pedir con los datos nuevos.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './cliente.ts'
import type { Aptitud, Centro, LecturaKm, Panel, TipoVehiculo, Usuario, Vehiculo, Vencimiento } from './tipos.ts'

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
