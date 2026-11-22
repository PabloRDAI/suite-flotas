// Ficha de un vehículo: aptitud para salir (FLO-07) y pestañas de datos,
// documentación (FLO-06), asignaciones de conductor (PER-03, PER-04), mantenimiento
// preventivo (MAN-01) y lecturas de km (FLO-05).

import {
  Alert,
  Anchor,
  Button,
  Group,
  List,
  NumberInput,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconCircleCheck,
  IconCircleX,
  IconFileCertificate,
  IconGauge,
  IconInfoCircle,
  IconSteeringWheel,
  IconTool,
} from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { ErrorApi } from '../api/cliente.ts'
import {
  useAptitud,
  useAsignacionesVehiculo,
  useHistorial,
  usePreventivos,
  useCentros,
  useLecturasKm,
  useRegistrarLectura,
  useTiposVehiculo,
  useVehiculo,
  useVencimientos,
} from '../api/consultas.ts'
import type { Aptitud, Vehiculo } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarFlota, puedeGestionarTaller } from '../auth/permisos.ts'
import { AsignarConductor } from '../componentes/AsignarConductor.tsx'
import { BotonCrearOTPlan } from '../componentes/BotonCrearOTPlan.tsx'
import { BotonRealizado } from '../componentes/BotonRealizado.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { Documentacion } from '../componentes/Documentacion.tsx'
import { HistorialAsignaciones } from '../componentes/HistorialAsignaciones.tsx'
import { EstadoOT, EstadoVehiculo, IndicadorPreventivo, TipoOrden } from '../componentes/Indicadores.tsx'
import { etiqueta, formatoEuros, formatoFecha, formatoKm, formatoNumero, hoyIso } from '../util/formato.ts'

export default function FichaVehiculo() {
  const id = Number(useParams().id)
  const vehiculo = useVehiculo(id)
  const aptitud = useAptitud(id)
  const asignaciones = useAsignacionesVehiculo(id)
  const vencimientos = useVencimientos(id)
  const habitual = asignaciones.data?.find((a) => a.vigente && a.habitual)

  if (vehiculo.isPending) return <Cargando />
  if (vehiculo.error) {
    const noExiste = vehiculo.error instanceof ErrorApi && vehiculo.error.status === 404
    return (
      <Stack>
        <VolverAlListado />
        {noExiste ? <Alert color="gray">Este vehículo no existe o no es de tu empresa.</Alert> : <ErrorCarga error={vehiculo.error} />}
      </Stack>
    )
  }

  const v = vehiculo.data
  return (
    <Stack>
      <VolverAlListado />
      <Group gap="sm" align="center">
        <Title order={2} ff="monospace">
          {v.matricula}
        </Title>
        <EstadoVehiculo valor={v.estado} />
      </Group>
      <Text c="dimmed" mt={-12}>
        {v.marca} {v.modelo} · {v.anio}
        {habitual && (
          <>
            {' · Conductor/a habitual: '}
            <Anchor component={Link} to={`/personal/${habitual.persona_id}`}>
              {habitual.persona_nombre}
            </Anchor>
          </>
        )}
      </Text>

      {aptitud.data && <AvisoAptitud aptitud={aptitud.data} />}

      <Tabs defaultValue="datos" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="datos" leftSection={<IconInfoCircle size={16} />}>
            Datos
          </Tabs.Tab>
          <Tabs.Tab value="documentacion" leftSection={<IconFileCertificate size={16} />}>
            Documentación
          </Tabs.Tab>
          <Tabs.Tab value="asignaciones" leftSection={<IconSteeringWheel size={16} />}>
            Asignaciones
          </Tabs.Tab>
          <Tabs.Tab value="mantenimiento" leftSection={<IconTool size={16} />}>
            Mantenimiento
          </Tabs.Tab>
          <Tabs.Tab value="km" leftSection={<IconGauge size={16} />}>
            Km
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="datos" pt="md">
          <PestanaDatos vehiculo={v} />
        </Tabs.Panel>
        <Tabs.Panel value="documentacion" pt="md">
          <Documentacion consulta={vencimientos} />
        </Tabs.Panel>
        <Tabs.Panel value="asignaciones" pt="md">
          <PestanaAsignaciones vehiculo={v} />
        </Tabs.Panel>
        <Tabs.Panel value="mantenimiento" pt="md">
          <Stack gap="xl">
            <PestanaMantenimiento vehiculo={v} />
            <HistorialMantenimiento vehiculoId={v.id} />
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="km" pt="md">
          <PestanaKm vehiculo={v} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

function VolverAlListado() {
  return (
    <Anchor component={Link} to="/vehiculos" size="sm">
      <Group gap={4}>
        <IconArrowLeft size={16} /> Vehículos
      </Group>
    </Anchor>
  )
}

/** FLO-07: ¿puede salir? Con los motivos si no puede, y aviso si algo caduca pronto. */
function AvisoAptitud({ aptitud }: { aptitud: Aptitud }) {
  if (!aptitud.apto) {
    return (
      <Alert color="red" icon={<IconCircleX />} title="No apto para salir">
        <List size="sm">
          {aptitud.motivos.map((m) => (
            <List.Item key={m}>{m}</List.Item>
          ))}
        </List>
      </Alert>
    )
  }
  if (aptitud.semaforo === 'ambar') {
    return (
      <Alert color="yellow" icon={<IconAlertTriangle />} title="Apto para salir">
        Tiene documentación que caduca pronto: revisa la pestaña Documentación.
      </Alert>
    )
  }
  return (
    <Alert color="green" icon={<IconCircleCheck />} title="Apto para salir">
      Operativo y con la documentación en regla.
    </Alert>
  )
}

function Dato({ etiqueta: nombre, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {nombre}
      </Text>
      <Text>{valor}</Text>
    </div>
  )
}

function PestanaDatos({ vehiculo: v }: { vehiculo: Vehiculo }) {
  const centros = useCentros()
  const tipos = useTiposVehiculo()
  const tipo = tipos.data?.find((t) => t.id === v.tipo_id)
  const centro = centros.data?.find((c) => c.id === v.centro_id)
  const capacidad =
    v.capacidad === null ? '—' : `${formatoNumero(v.capacidad)} ${tipo?.unidad_capacidad === 'kg' ? 'kg' : 'plazas'}`

  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="lg">
      <Dato etiqueta="Matrícula" valor={v.matricula} />
      <Dato etiqueta="Tipo" valor={tipo?.nombre ?? '—'} />
      <Dato etiqueta="Centro" valor={centro?.nombre ?? '—'} />
      <Dato etiqueta="Marca" valor={v.marca} />
      <Dato etiqueta="Modelo" valor={v.modelo} />
      <Dato etiqueta="Año" valor={String(v.anio)} />
      <Dato etiqueta="Capacidad" valor={capacidad} />
      <Dato etiqueta="Combustible" valor={etiqueta(v.combustible)} />
      <Dato etiqueta="Km actuales" valor={formatoKm(v.km_actuales)} />
    </SimpleGrid>
  )
}

/** PER-03 y PER-04: historial de conductores y, para admin y tráfico, el formulario de asignación. */
function PestanaAsignaciones({ vehiculo }: { vehiculo: Vehiculo }) {
  const { usuario } = useSesion()
  const asignaciones = useAsignacionesVehiculo(vehiculo.id)
  const gestiona = puedeGestionarFlota(usuario) && vehiculo.activo

  if (asignaciones.isPending) return <Cargando />
  if (asignaciones.error) return <ErrorCarga error={asignaciones.error} />
  return (
    <Stack>
      {gestiona && <AsignarConductor vehiculoId={vehiculo.id} asignaciones={asignaciones.data} />}
      <HistorialAsignaciones asignaciones={asignaciones.data} mostrar="conductor" puedeFinalizar={gestiona} />
    </Stack>
  )
}

/** MAN-01: los planes preventivos del vehículo, con su situación (vencidos primero). */
function PestanaMantenimiento({ vehiculo }: { vehiculo: Vehiculo }) {
  const { usuario } = useSesion()
  const preventivos = usePreventivos(vehiculo.id)
  const gestiona = puedeGestionarTaller(usuario) && vehiculo.activo

  if (preventivos.isPending) return <Cargando />
  if (preventivos.error) return <ErrorCarga error={preventivos.error} />
  if (preventivos.data.length === 0) return <Text c="dimmed">No hay planes de mantenimiento para este tipo de vehículo.</Text>

  const intervalo = (km: number | null, dias: number | null) =>
    [km ? formatoKm(km) : null, dias ? `${dias} días` : null].filter(Boolean).join(' o ')

  return (
    <Table.ScrollContainer minWidth={820}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Plan</Table.Th>
            <Table.Th>Situación</Table.Th>
            <Table.Th>Último</Table.Th>
            <Table.Th>Próximo</Table.Th>
            <Table.Th>Motivo</Table.Th>
            {gestiona && <Table.Th />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {preventivos.data.map((p) => (
            <Table.Tr key={p.plan_id}>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {p.plan_nombre}
                </Text>
                <Text size="xs" c="dimmed">
                  Cada {intervalo(p.intervalo_km, p.intervalo_dias)}
                </Text>
              </Table.Td>
              <Table.Td>
                <IndicadorPreventivo valor={p.situacion} />
              </Table.Td>
              <Table.Td>
                {formatoFecha(p.ultima_fecha)} · {formatoKm(p.ultimos_km)}
              </Table.Td>
              <Table.Td>
                {[p.proxima_fecha ? formatoFecha(p.proxima_fecha) : null, p.proximos_km !== null ? formatoKm(p.proximos_km) : null]
                  .filter(Boolean)
                  .join(' o ')}
              </Table.Td>
              <Table.Td>{p.motivo}</Table.Td>
              {gestiona && (
                <Table.Td>
                  <Group gap={6} wrap="nowrap">
                    <BotonCrearOTPlan p={{ vehiculo_id: vehiculo.id, plan_id: p.plan_id, plan_nombre: p.plan_nombre, matricula: vehiculo.matricula }} />
                    <BotonRealizado
                      vehiculoId={vehiculo.id}
                      matricula={vehiculo.matricula}
                      planId={p.plan_id}
                      planNombre={p.plan_nombre}
                      kmActuales={vehiculo.km_actuales}
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
  )
}

/** MAN-07: "la ficha del vehículo lista todas sus OT con fecha, tipo, km y coste". */
function HistorialMantenimiento({ vehiculoId }: { vehiculoId: number }) {
  const historial = useHistorial(vehiculoId)
  if (historial.isPending) return <Cargando />
  if (historial.error) return <ErrorCarga error={historial.error} />
  const { resumen, ordenes } = historial.data
  return (
    <Stack gap="xs">
      <Group justify="space-between" align="baseline">
        <Title order={3} size="h5">
          Historial de mantenimiento
        </Title>
        <Text size="sm" c="dimmed">
          {resumen.cerradas} OT cerradas · {formatoEuros(resumen.coste_total)} (preventivo {formatoEuros(resumen.coste_preventivo)} ·
          correctivo {formatoEuros(resumen.coste_correctivo)})
        </Text>
      </Group>
      {ordenes.length === 0 ? (
        <Text c="dimmed">Sin órdenes de trabajo.</Text>
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Tipo</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Descripción</Table.Th>
                <Table.Th ta="right">Km</Table.Th>
                <Table.Th ta="right">Coste</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {ordenes.map((o) => (
                <Table.Tr key={o.ot_id}>
                  <Table.Td>
                    <Anchor component={Link} to={`/ordenes-trabajo/${o.ot_id}`}>
                      {formatoFecha(o.fecha)}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>
                    <TipoOrden valor={o.tipo} />
                  </Table.Td>
                  <Table.Td>
                    <EstadoOT valor={o.estado} />
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" lineClamp={1}>
                      {o.descripcion}
                    </Text>
                  </Table.Td>
                  <Table.Td ta="right">{o.km !== null ? formatoKm(o.km) : '—'}</Table.Td>
                  <Table.Td ta="right">{formatoEuros(o.coste)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}

/** FLO-05: historial de lecturas y formulario para registrar una nueva. */
function PestanaKm({ vehiculo }: { vehiculo: Vehiculo }) {
  const lecturas = useLecturasKm(vehiculo.id)
  const registrar = useRegistrarLectura(vehiculo.id)
  const [km, setKm] = useState<number | string>('')
  const [fecha, setFecha] = useState(hoyIso())

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    registrar.mutate(
      { km: Number(km), fecha },
      {
        onSuccess: () => {
          notifications.show({ color: 'green', message: `Lectura de ${formatoKm(Number(km))} registrada` })
          setKm('')
        },
      },
    )
  }

  return (
    <Stack>
      {vehiculo.activo && (
        <form onSubmit={enviar}>
          <Group align="end" gap="sm">
            <NumberInput
              label="Km del cuentakilómetros"
              required
              min={0}
              thousandSeparator="."
              decimalSeparator=","
              allowDecimal={false}
              value={km}
              onChange={setKm}
              w={{ base: '100%', xs: 200 }}
            />
            <TextInput
              label="Fecha"
              type="date"
              required
              max={hoyIso()}
              value={fecha}
              onChange={(e) => setFecha(e.currentTarget.value)}
              w={{ base: '100%', xs: 170 }}
            />
            <Button type="submit" loading={registrar.isPending}>
              Registrar lectura
            </Button>
          </Group>
          {/* El mensaje de la regla de negocio llega tal cual desde la API (p. ej. km menores que la anterior). */}
          {registrar.error && (
            <Alert color="red" mt="sm" role="alert">
              {registrar.error.message}
            </Alert>
          )}
        </form>
      )}

      {lecturas.isPending && <Cargando />}
      {lecturas.error && <ErrorCarga error={lecturas.error} />}
      {lecturas.data && (
        <Table.ScrollContainer minWidth={320}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Fecha</Table.Th>
                <Table.Th ta="right">Km</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {lecturas.data.map((l) => (
                <Table.Tr key={l.id}>
                  <Table.Td>{formatoFecha(l.fecha)}</Table.Td>
                  <Table.Td ta="right">{formatoKm(l.km)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
