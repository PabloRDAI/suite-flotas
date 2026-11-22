// Botón "Exportar a Excel" de los listados (GEN-06).
//
// Pide el .xlsx a la API con los MISMOS filtros que tiene la pantalla en ese momento
// (por eso recibe los filtros, no los datos): el archivo trae lo que se está viendo.

import { Button, Group, Text } from '@mantine/core'
import { IconFileSpreadsheet } from '@tabler/icons-react'
import { useState } from 'react'
import { guardarArchivo } from '../api/cliente.ts'

type Filtros = Record<string, string | number | boolean | null | undefined>

/** "/vehiculos/exportar" + { centro_id: 3, buscar: '' } -> "/vehiculos/exportar?centro_id=3" (los vacíos no se envían). */
function rutaConFiltros(ruta: string, filtros: Filtros = {}): string {
  const parametros = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== null && valor !== undefined && valor !== '') parametros.set(clave, String(valor))
  }
  return parametros.size ? `${ruta}?${parametros}` : ruta
}

export function BotonExportar({ ruta, filtros, nombre }: { ruta: string; filtros?: Filtros; nombre: string }) {
  const [descargando, setDescargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exportar = async () => {
    setDescargando(true)
    setError(null)
    try {
      await guardarArchivo(rutaConFiltros(ruta, filtros), `${nombre}.xlsx`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido descargar el archivo')
    } finally {
      setDescargando(false)
    }
  }

  return (
    <Group gap={6} wrap="nowrap">
      {error && (
        <Text size="xs" c="red" role="alert">
          {error}
        </Text>
      )}
      <Button variant="default" leftSection={<IconFileSpreadsheet size={16} />} loading={descargando} onClick={exportar} title="Descarga un Excel con lo que se ve, con los filtros aplicados">
        Exportar a Excel
      </Button>
    </Group>
  )
}
