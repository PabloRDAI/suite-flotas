// Documentación con semáforo (FLO-06 para vehículos, PER-02 para personas).
// Mismo componente para los dos: "mismas reglas de colores" también en la interfaz.

import { Stack, Switch, Table, Text } from '@mantine/core'
import type { UseQueryResult } from '@tanstack/react-query'
import { useState } from 'react'
import type { Vencimiento } from '../api/tipos.ts'
import { formatoFecha } from '../util/formato.ts'
import { Cargando, ErrorCarga } from './Carga.tsx'
import { IndicadorSemaforo } from './Indicadores.tsx'

/** Por defecto solo los documentos vigentes; el historial (ya renovados), opcional. */
export function Documentacion({ consulta }: { consulta: UseQueryResult<Vencimiento[], Error> }) {
  const [verHistorial, setVerHistorial] = useState(false)

  if (consulta.isPending) return <Cargando />
  if (consulta.error) return <ErrorCarga error={consulta.error} />

  const filas = consulta.data.filter((v) => verHistorial || v.vigente)
  return (
    <Stack>
      <Switch
        label="Ver documentos anteriores (ya renovados)"
        checked={verHistorial}
        onChange={(e) => setVerHistorial(e.currentTarget.checked)}
      />
      {filas.length === 0 ? (
        <Text c="dimmed">No hay documentación registrada.</Text>
      ) : (
        <Table.ScrollContainer minWidth={520}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Documento</Table.Th>
                <Table.Th>Caduca</Table.Th>
                <Table.Th ta="right">Días</Table.Th>
                <Table.Th>Semáforo</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filas.map((v) => (
                <Table.Tr key={v.id} c={v.vigente ? undefined : 'dimmed'}>
                  <Table.Td>
                    {v.tipo_nombre}
                    {!v.vigente && ' (renovado)'}
                  </Table.Td>
                  <Table.Td>{formatoFecha(v.fecha_caducidad)}</Table.Td>
                  <Table.Td ta="right">{v.dias_restantes}</Table.Td>
                  <Table.Td>{v.vigente ? <IndicadorSemaforo valor={v.semaforo} /> : '—'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
