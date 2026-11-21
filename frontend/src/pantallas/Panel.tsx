// Panel de flota (FLO-04): contadores por estado, alertas y tabla filtrable.
//
// Todo llega en UNA petición (GET /panel) calculada en el servidor. Las tarjetas de
// contadores filtran la tabla al pulsarlas, así que número y filas siempre coinciden.

import {
  Anchor,
  Badge,
  Card,
  Group,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { IconAlertTriangle, IconCircleCheck, IconCircleX, IconTool } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useCentros, usePanel, useTiposVehiculo } from '../api/consultas.ts'
import type { AlertaPanel, Panel as DatosPanel, VehiculoPanel } from '../api/tipos.ts'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { EstadoVehiculo, IndicadorSemaforo } from '../componentes/Indicadores.tsx'
import { formatoFecha, formatoKm } from '../util/formato.ts'

// Qué muestra la tabla según la tarjeta pulsada.
type Vista = 'todos' | 'operativo' | 'en_taller' | 'inmovilizado' | 'no_aptos'

const FILTRO_VISTA: Record<Vista, (v: VehiculoPanel) => boolean> = {
  todos: () => true,
  operativo: (v) => v.estado === 'operativo',
  en_taller: (v) => v.estado === 'en_taller',
  inmovilizado: (v) => v.estado === 'inmovilizado',
  no_aptos: (v) => !v.apto,
}

export default function Panel() {
  const [centroId, setCentroId] = useState<string | null>(null)
  const [tipoId, setTipoId] = useState<string | null>(null)
  const [vista, setVista] = useState<Vista>('todos')

  const panel = usePanel(centroId, tipoId)
  const centros = useCentros()
  const tipos = useTiposVehiculo()

  return (
    <Stack>
      <Group justify="space-between" align="end">
        <div>
          <Title order={2}>Panel de flota</Title>
          {panel.data && (
            <Text c="dimmed" size="sm">
              Situación a {formatoFecha(panel.data.fecha)}
            </Text>
          )}
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

      {panel.isPending && <Cargando />}
      {panel.error && <ErrorCarga error={panel.error} />}
      {panel.data && (
        <>
          <Contadores datos={panel.data} vista={vista} alElegir={setVista} />
          <Alertas alertas={panel.data.alertas} />
          <TablaVehiculos
            vehiculos={panel.data.vehiculos.filter(FILTRO_VISTA[vista])}
            vista={vista}
            nombreCentro={new Map(centros.data?.map((c) => [c.id, c.nombre]))}
            nombreTipo={new Map(tipos.data?.map((t) => [t.id, t.nombre]))}
          />
        </>
      )}
    </Stack>
  )
}

// --- Contadores --------------------------------------------------------------

function Contadores({ datos, vista, alElegir }: { datos: DatosPanel; vista: Vista; alElegir: (v: Vista) => void }) {
  const c = datos.contadores
  const tarjetas: { vista: Vista; texto: string; valor: number; color: string }[] = [
    { vista: 'todos', texto: 'Total', valor: c.total, color: 'indigo' },
    { vista: 'operativo', texto: 'Operativos', valor: c.operativo, color: 'green' },
    { vista: 'en_taller', texto: 'En taller', valor: c.en_taller, color: 'orange' },
    { vista: 'inmovilizado', texto: 'Inmovilizados', valor: c.inmovilizado, color: 'red' },
    { vista: 'no_aptos', texto: 'No aptos para salir', valor: c.no_aptos, color: 'red' },
  ]
  return (
    <SimpleGrid cols={{ base: 2, sm: 3, lg: 5 }}>
      {tarjetas.map((t) => {
        const activa = vista === t.vista
        return (
          // Botón real: se puede pulsar con ratón, teclado o lector de pantalla.
          <UnstyledButton key={t.vista} onClick={() => alElegir(activa ? 'todos' : t.vista)} aria-pressed={activa}>
            <Card withBorder padding="md" style={{ borderColor: activa ? `var(--mantine-color-${t.color}-6)` : undefined, borderWidth: activa ? 2 : 1 }}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
                {t.texto}
              </Text>
              <Text fz={32} fw={700} c={t.valor > 0 && t.vista !== 'todos' && t.vista !== 'operativo' ? t.color : undefined}>
                {t.valor}
              </Text>
            </Card>
          </UnstyledButton>
        )
      })}
    </SimpleGrid>
  )
}

// --- Alertas -----------------------------------------------------------------

function Alertas({ alertas }: { alertas: AlertaPanel[] }) {
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          Alertas
        </Title>
        <Badge variant="light" color={alertas.length ? 'red' : 'green'}>
          {alertas.length}
        </Badge>
      </Group>
      {alertas.length === 0 ? (
        <Group gap="xs" c="green">
          <IconCircleCheck size={18} aria-hidden />
          <Text>Nada pendiente: documentación en regla y mantenimiento al día.</Text>
        </Group>
      ) : (
        <Stack gap={6}>
          {alertas.map((a) => (
            <Group key={`${a.vehiculo_id}-${a.mensaje}`} gap="sm" wrap="nowrap">
              {/* Documentación: ❌/⚠️ · Preventivo: 🔧. El color dice la gravedad; el texto, el qué. */}
              <ThemeIcon variant="light" color={a.semaforo === 'rojo' ? 'red' : 'yellow'} size="sm" aria-hidden>
                {a.tipo === 'preventivo' ? (
                  <IconTool size={14} />
                ) : a.semaforo === 'rojo' ? (
                  <IconCircleX size={14} />
                ) : (
                  <IconAlertTriangle size={14} />
                )}
              </ThemeIcon>
              <Anchor component={Link} to={`/vehiculos/${a.vehiculo_id}`} ff="monospace" fw={600}>
                {a.matricula}
              </Anchor>
              <Text size="sm">{a.mensaje}</Text>
              {a.fecha && (
                <Text size="xs" c="dimmed" visibleFrom="sm">
                  ({formatoFecha(a.fecha)})
                </Text>
              )}
            </Group>
          ))}
        </Stack>
      )}
    </Card>
  )
}

// --- Tabla -------------------------------------------------------------------

// Orden de urgencia del semáforo para ordenar la tabla.
const orden = { rojo: 0, ambar: 1, verde: 2 } as const

function TablaVehiculos({
  vehiculos,
  vista,
  nombreCentro,
  nombreTipo,
}: {
  vehiculos: VehiculoPanel[]
  vista: Vista
  nombreCentro: Map<number, string>
  nombreTipo: Map<number, string>
}) {
  const ordenados = useMemo(
    // Primero los que necesitan atención: no aptos, luego semáforo rojo/ámbar.
    () => [...vehiculos].sort((a, b) => Number(a.apto) - Number(b.apto) || orden[a.semaforo] - orden[b.semaforo] || a.matricula.localeCompare(b.matricula)),
    [vehiculos],
  )
  return (
    <Card withBorder padding={0}>
      <Group justify="space-between" p="md" pb={0}>
        <Title order={3} size="h4">
          Vehículos
        </Title>
        <Text size="sm" c="dimmed">
          {vista === 'todos' ? `${vehiculos.length} vehículos` : `${vehiculos.length} con el filtro de la tarjeta`}
        </Text>
      </Group>
      <Table.ScrollContainer minWidth={760}>
        <Table striped highlightOnHover verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Matrícula</Table.Th>
              <Table.Th>Tipo</Table.Th>
              <Table.Th>Centro</Table.Th>
              <Table.Th ta="right">Km</Table.Th>
              <Table.Th>Estado</Table.Th>
              <Table.Th>¿Puede salir?</Table.Th>
              <Table.Th>Documentación</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {ordenados.map((v) => (
              <Table.Tr key={v.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/vehiculos/${v.id}`} ff="monospace" fw={600}>
                    {v.matricula}
                  </Anchor>
                </Table.Td>
                <Table.Td>{nombreTipo.get(v.tipo_id) ?? '—'}</Table.Td>
                <Table.Td>{nombreCentro.get(v.centro_id) ?? '—'}</Table.Td>
                <Table.Td ta="right">{formatoKm(v.km_actuales)}</Table.Td>
                <Table.Td>
                  <EstadoVehiculo valor={v.estado} />
                </Table.Td>
                <Table.Td>
                  <Apto vehiculo={v} />
                </Table.Td>
                <Table.Td>
                  <IndicadorSemaforo valor={v.semaforo} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Card>
  )
}

/** "Apto" / "No apto" con icono; al pasar el ratón (o enfocar), se ven los motivos. */
function Apto({ vehiculo }: { vehiculo: VehiculoPanel }) {
  if (vehiculo.apto) {
    return (
      <Badge color="green" variant="outline" leftSection={<IconCircleCheck size={14} aria-hidden />}>
        Apto
      </Badge>
    )
  }
  return (
    <Tooltip label={vehiculo.motivos.join(' · ')} multiline maw={300} withArrow>
      <Badge color="red" leftSection={<IconCircleX size={14} aria-hidden />} tabIndex={0} aria-label={`No apto: ${vehiculo.motivos.join('. ')}`}>
        No apto
      </Badge>
    </Tooltip>
  )
}
