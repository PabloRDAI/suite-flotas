// Taller (pantalla 4 de la spec): tablero de órdenes de trabajo por estado y previsión de preventivos.
//
// - Tablero: Abiertas -> En curso -> Cerradas (últimos 30 días). Cada tarjeta lleva a su OT.
// - Previsión (MAN-02): ya ordenada por urgencia desde el backend; desde cada fila se puede
//   crear la OT preventiva del plan o registrar que ya se hizo.

import {
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Modal,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  Title,
  Tooltip,
} from '@mantine/core'
import { IconCircleCheck, IconHandStop, IconLayoutKanban, IconListCheck, IconPlus } from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useCentros, useCrearOT, useOrdenes, usePrevision, useTiposVehiculo, useVehiculos } from '../api/consultas.ts'
import type { OrdenTrabajo, TipoOT } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarTaller } from '../auth/permisos.ts'
import { BotonCrearOTPlan } from '../componentes/BotonCrearOTPlan.tsx'
import { BotonRealizado } from '../componentes/BotonRealizado.tsx'
import { BotonExportar } from '../componentes/BotonExportar.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { IndicadorPreventivo, TipoOrden } from '../componentes/Indicadores.tsx'
import { formatoEuros, formatoFecha, formatoKm } from '../util/formato.ts'

const hace30Dias = () => {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function Taller() {
  const { usuario } = useSesion()
  const gestiona = puedeGestionarTaller(usuario)
  return (
    <Stack>
      <Title order={2}>Taller</Title>
      <Tabs defaultValue="tablero" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="tablero" leftSection={<IconLayoutKanban size={16} />}>
            Tablero de OT
          </Tabs.Tab>
          <Tabs.Tab value="prevision" leftSection={<IconListCheck size={16} />}>
            Previsión de preventivos
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="tablero" pt="md">
          <Tablero gestiona={gestiona} />
        </Tabs.Panel>
        <Tabs.Panel value="prevision" pt="md">
          <Prevision gestiona={gestiona} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

// --- Tablero de OT por estado ------------------------------------------------

function Tablero({ gestiona }: { gestiona: boolean }) {
  const desde = hace30Dias()
  const abiertas = useOrdenes({ abiertas: true })
  const cerradas = useOrdenes({ cerradasDesde: desde })
  const [nueva, setNueva] = useState(false)

  if (abiertas.isPending || cerradas.isPending) return <Cargando />
  if (abiertas.error) return <ErrorCarga error={abiertas.error} />
  if (cerradas.error) return <ErrorCarga error={cerradas.error} />

  const columnas = [
    { titulo: 'Abiertas', color: 'yellow', ordenes: abiertas.data.filter((o) => o.estado === 'abierta') },
    { titulo: 'En curso', color: 'blue', ordenes: abiertas.data.filter((o) => o.estado === 'en_curso') },
    { titulo: 'Cerradas (30 días)', color: 'green', ordenes: cerradas.data },
  ]
  return (
    <Stack>
      <Group justify="flex-end">
        {/* El Excel trae lo mismo que el tablero: abiertas, en curso y cerradas en 30 días. */}
        <BotonExportar ruta="/ordenes-trabajo/exportar" nombre="ordenes-de-trabajo" filtros={{ abiertas: true, cerradas_desde: desde }} />
        {gestiona && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setNueva(true)}>
            Nueva OT
          </Button>
        )}
      </Group>
      {/* En el móvil las columnas se apilan una debajo de otra. */}
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
        {columnas.map(({ titulo, color, ordenes }) => (
          <Card key={titulo} withBorder bg="var(--mantine-color-default-hover)" padding="sm">
            <Group justify="space-between" mb="sm">
              <Text fw={700}>{titulo}</Text>
              <Badge color={color} variant="light">
                {ordenes.length}
              </Badge>
            </Group>
            <Stack gap="xs">
              {ordenes.map((o) => (
                <TarjetaOT key={o.id} ot={o} />
              ))}
              {ordenes.length === 0 && (
                <Text size="sm" c="dimmed" ta="center" py="md">
                  Ninguna
                </Text>
              )}
            </Stack>
          </Card>
        ))}
      </SimpleGrid>
      <ModalNuevaOT abierto={nueva} cerrar={() => setNueva(false)} />
    </Stack>
  )
}

function TarjetaOT({ ot }: { ot: OrdenTrabajo }) {
  return (
    <Card withBorder padding="sm" component={Link} to={`/ordenes-trabajo/${ot.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Text ff="monospace" fw={700}>
          {ot.matricula}
        </Text>
        <TipoOrden valor={ot.tipo} />
      </Group>
      <Text size="sm" lineClamp={2} mt={4}>
        {ot.descripcion}
      </Text>
      <Group justify="space-between" mt={6}>
        <Text size="xs" c="dimmed">
          n.º {ot.id} · {ot.fecha_cierre ? `cerrada ${formatoFecha(ot.fecha_cierre)}` : `abierta ${new Date(ot.abierta_en).toLocaleDateString('es-ES')}`}
        </Text>
        <Group gap={6}>
          {ot.inmoviliza && ot.estado !== 'cerrada' && (
            <Tooltip label="Inmoviliza el vehículo">
              <IconHandStop size={16} color="var(--mantine-color-orange-6)" aria-label="Inmoviliza el vehículo" />
            </Tooltip>
          )}
          <Text size="sm" fw={600}>
            {formatoEuros(ot.coste.total)}
          </Text>
        </Group>
      </Group>
    </Card>
  )
}

/** OT manual: vehículo, tipo, descripción y si inmoviliza. Al crearla, se abre su ficha. */
function ModalNuevaOT({ abierto, cerrar }: { abierto: boolean; cerrar: () => void }) {
  const vehiculos = useVehiculos(false)
  const crear = useCrearOT()
  const navegar = useNavigate()
  const [vehiculoId, setVehiculoId] = useState<string | null>(null)
  const [tipo, setTipo] = useState<TipoOT>('correctiva')
  const [descripcion, setDescripcion] = useState('')
  const [inmoviliza, setInmoviliza] = useState(false)

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    if (!vehiculoId) return
    crear.mutate(
      { vehiculo_id: Number(vehiculoId), tipo, descripcion, inmoviliza },
      {
        onSuccess: (ot) => {
          cerrar()
          void navegar(`/ordenes-trabajo/${ot.id}`)
        },
      },
    )
  }

  return (
    <Modal opened={abierto} onClose={cerrar} title="Nueva orden de trabajo" centered>
      <form onSubmit={enviar}>
        <Stack>
          <Select
            label="Vehículo"
            required
            searchable
            data={vehiculos.data?.map((v) => ({ value: String(v.id), label: `${v.matricula} · ${v.marca} ${v.modelo}` })) ?? []}
            value={vehiculoId}
            onChange={setVehiculoId}
          />
          <SegmentedControl
            value={tipo}
            onChange={(v) => setTipo(v as TipoOT)}
            data={[
              { value: 'correctiva', label: 'Correctiva' },
              { value: 'preventiva', label: 'Preventiva' },
            ]}
          />
          <Textarea label="Qué hay que hacer" required autosize minRows={2} maxLength={2000} value={descripcion} onChange={(e) => setDescripcion(e.currentTarget.value)} />
          <Checkbox
            label="Inmoviliza el vehículo"
            description="Mientras la OT esté abierta o en curso, el vehículo estará en taller y no podrá salir."
            checked={inmoviliza}
            onChange={(e) => setInmoviliza(e.currentTarget.checked)}
          />
          {crear.error && <Text c="red" size="sm">{crear.error.message}</Text>}
          <Group justify="flex-end">
            <Button variant="default" onClick={cerrar}>
              Cancelar
            </Button>
            <Button type="submit" loading={crear.isPending} disabled={!vehiculoId}>
              Crear OT
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}

// --- Previsión de preventivos (MAN-02) ---------------------------------------

function Prevision({ gestiona }: { gestiona: boolean }) {
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
        <Text c="dimmed" size="sm">
          Lo vencido y lo que toca en los próximos 30 días o 2.000 km · {vencidos} vencidos · {proximos} próximos
        </Text>
        <Group gap="sm" align="end">
          <Select label="Centro" placeholder="Todos" clearable data={centros.data?.map((c) => ({ value: String(c.id), label: c.nombre })) ?? []} value={centroId} onChange={setCentroId} w={180} />
          <Select label="Tipo" placeholder="Todos" clearable data={tipos.data?.map((t) => ({ value: String(t.id), label: t.nombre })) ?? []} value={tipoId} onChange={setTipoId} w={160} />
          <BotonExportar ruta="/preventivos/prevision/exportar" nombre="prevision-preventivos" filtros={{ centro_id: centroId, tipo_id: tipoId }} />
        </Group>
      </Group>
      {prevision.isPending && <Cargando />}
      {prevision.error && <ErrorCarga error={prevision.error} />}
      {prevision.data?.length === 0 && (
        <Group gap="xs" c="green">
          <IconCircleCheck size={18} aria-hidden />
          <Text>Todo al día: no hay preventivos vencidos ni previstos.</Text>
        </Group>
      )}
      {!!prevision.data?.length && (
        <Table.ScrollContainer minWidth={880}>
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
                      <Group gap={6} wrap="nowrap">
                        <BotonCrearOTPlan p={p} />
                        <BotonRealizado
                          vehiculoId={p.vehiculo_id}
                          matricula={p.matricula}
                          planId={p.plan_id}
                          planNombre={p.plan_nombre}
                          kmActuales={p.km_actuales}
                          tareas={p.tareas}
                        />
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
