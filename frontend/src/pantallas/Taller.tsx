// Taller: previsión de preventivos (MAN-02). Más adelante, también el tablero de órdenes de trabajo.
//
// La lista llega del backend ya ordenada por urgencia (lo vencido y más atrasado primero),
// calculada por el motor de reglas: aquí no se reordena.

import { Anchor, Card, Group, Select, Stack, Table, Text, Title, Tooltip } from '@mantine/core'
import { IconCircleCheck } from '@tabler/icons-react'
import { Link } from 'react-router'
import { useState } from 'react'
import { useCentros, usePrevision, useTiposVehiculo } from '../api/consultas.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarTaller } from '../auth/permisos.ts'
import { BotonRealizado } from '../componentes/BotonRealizado.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { IndicadorPreventivo } from '../componentes/Indicadores.tsx'
import { formatoFecha, formatoKm } from '../util/formato.ts'

export default function Taller() {
  const { usuario } = useSesion()
  const gestiona = puedeGestionarTaller(usuario)
  const [centroId, setCentroId] = useState<string | null>(null)
  const [tipoId, setTipoId] = useState<string | null>(null)

  const prevision = usePrevision(centroId, tipoId)
  const centros = useCentros()
  const tipos = useTiposVehiculo()
  const nombreTipo = new Map(tipos.data?.map((t) => [t.id, t.nombre]))

  const vencidos = prevision.data?.filter((p) => p.situacion === 'vencido').length ?? 0
  const proximos = (prevision.data?.length ?? 0) - vencidos

  return (
    <Stack>
      <Group justify="space-between" align="end">
        <div>
          <Title order={2}>Taller</Title>
          <Text c="dimmed" size="sm">
            Previsión de preventivos: lo vencido y lo que toca en los próximos 30 días o 2.000 km
          </Text>
        </div>
        <Group gap="sm" align="end">
          <Select
            label="Centro"
            placeholder="Todos"
            clearable
            data={centros.data?.map((c) => ({ value: String(c.id), label: c.nombre })) ?? []}
            value={centroId}
            onChange={setCentroId}
            w={180}
          />
          <Select
            label="Tipo"
            placeholder="Todos"
            clearable
            data={tipos.data?.map((t) => ({ value: String(t.id), label: t.nombre })) ?? []}
            value={tipoId}
            onChange={setTipoId}
            w={160}
          />
        </Group>
      </Group>

      {prevision.isPending && <Cargando />}
      {prevision.error && <ErrorCarga error={prevision.error} />}
      {prevision.data && (
        <Card withBorder padding={0}>
          <Group justify="space-between" p="md" pb={0}>
            <Title order={3} size="h4">
              Previsión de preventivos
            </Title>
            <Text size="sm" c="dimmed">
              {vencidos} vencidos · {proximos} próximos
            </Text>
          </Group>
          {prevision.data.length === 0 ? (
            <Group gap="xs" c="green" p="md">
              <IconCircleCheck size={18} aria-hidden />
              <Text>Todo al día: no hay preventivos vencidos ni previstos en los próximos 30 días o 2.000 km.</Text>
            </Group>
          ) : (
            <Table.ScrollContainer minWidth={820}>
              <Table striped highlightOnHover verticalSpacing="xs">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Situación</Table.Th>
                    <Table.Th>Vehículo</Table.Th>
                    <Table.Th>Plan</Table.Th>
                    <Table.Th>Motivo</Table.Th>
                    <Table.Th>Próxima fecha</Table.Th>
                    <Table.Th ta="right">Próximos km</Table.Th>
                    {gestiona && <Table.Th />}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {prevision.data.map((p) => (
                    <Table.Tr key={`${p.vehiculo_id}-${p.plan_id}`}>
                      <Table.Td>
                        <IndicadorPreventivo valor={p.situacion} />
                      </Table.Td>
                      <Table.Td>
                        <Anchor component={Link} to={`/vehiculos/${p.vehiculo_id}`} ff="monospace" fw={600}>
                          {p.matricula}
                        </Anchor>
                        <Text size="xs" c="dimmed">
                          {nombreTipo.get(p.tipo_id)} · {formatoKm(p.km_actuales)}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {/* Al pasar el ratón (o enfocar), las tareas del plan. */}
                        <Tooltip label={p.tareas.join(' · ') || 'Sin tareas definidas'} multiline maw={320} withArrow>
                          <Text size="sm" td="underline dotted" tabIndex={0} style={{ cursor: 'help' }}>
                            {p.plan_nombre}
                          </Text>
                        </Tooltip>
                      </Table.Td>
                      <Table.Td>{p.motivo}</Table.Td>
                      <Table.Td>{p.proxima_fecha ? formatoFecha(p.proxima_fecha) : '—'}</Table.Td>
                      <Table.Td ta="right">{p.proximos_km !== null ? formatoKm(p.proximos_km) : '—'}</Table.Td>
                      {gestiona && (
                        <Table.Td>
                          <BotonRealizado
                            vehiculoId={p.vehiculo_id}
                            matricula={p.matricula}
                            planId={p.plan_id}
                            planNombre={p.plan_nombre}
                            kmActuales={p.km_actuales}
                            tareas={p.tareas}
                          />
                        </Table.Td>
                      )}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
        </Card>
      )}
    </Stack>
  )
}
