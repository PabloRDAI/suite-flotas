// Ficha de un vehículo: aptitud para salir (FLO-07) y pestañas de datos,
// documentación (FLO-06) y lecturas de km (FLO-05).

import {
  Alert,
  Anchor,
  Button,
  Group,
  List,
  NumberInput,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle, IconArrowLeft, IconCircleCheck, IconCircleX, IconFileCertificate, IconGauge, IconInfoCircle } from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { ErrorApi } from '../api/cliente.ts'
import {
  useAptitud,
  useCentros,
  useLecturasKm,
  useRegistrarLectura,
  useTiposVehiculo,
  useVehiculo,
  useVencimientos,
} from '../api/consultas.ts'
import type { Aptitud, Vehiculo } from '../api/tipos.ts'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { EstadoVehiculo, IndicadorSemaforo } from '../componentes/Indicadores.tsx'
import { etiqueta, formatoFecha, formatoKm, formatoNumero, hoyIso } from '../util/formato.ts'

export default function FichaVehiculo() {
  const id = Number(useParams().id)
  const vehiculo = useVehiculo(id)
  const aptitud = useAptitud(id)

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
          <Tabs.Tab value="km" leftSection={<IconGauge size={16} />}>
            Km
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="datos" pt="md">
          <PestanaDatos vehiculo={v} />
        </Tabs.Panel>
        <Tabs.Panel value="documentacion" pt="md">
          <PestanaDocumentacion vehiculoId={v.id} />
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

/** FLO-06: documentos con semáforo. Por defecto solo los vigentes; el historial, opcional. */
function PestanaDocumentacion({ vehiculoId }: { vehiculoId: number }) {
  const vencimientos = useVencimientos(vehiculoId)
  const [verHistorial, setVerHistorial] = useState(false)

  if (vencimientos.isPending) return <Cargando />
  if (vencimientos.error) return <ErrorCarga error={vencimientos.error} />

  const filas = vencimientos.data.filter((v) => verHistorial || v.vigente)
  return (
    <Stack>
      <Switch label="Ver documentos anteriores (ya renovados)" checked={verHistorial} onChange={(e) => setVerHistorial(e.currentTarget.checked)} />
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
