// Una orden de trabajo (MAN-04 a MAN-06): datos, acciones según el estado y líneas de coste.
//
// Los botones siguen el flujo de MAN-05: abierta -> [Iniciar] -> en curso -> [Cerrar] -> cerrada
// (o [Cancelar] desde abierta o en curso). Una OT cerrada o cancelada es definitiva.

import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Modal,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft, IconHandStop, IconPlayerPlay, IconTrash } from '@tabler/icons-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ErrorApi } from '../api/cliente.ts'
import { useAccionOT, useAnadirLinea, useBorrarLinea, useOrden, useRecambios, useVehiculo } from '../api/consultas.ts'
import type { Concepto, OrdenTrabajo as OT } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarTaller } from '../auth/permisos.ts'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { EstadoOT, EstadoVehiculo, TipoOrden } from '../componentes/Indicadores.tsx'
import { formatoEuros, formatoFecha, formatoKm, hoyIso } from '../util/formato.ts'

const CONCEPTOS: { value: Concepto; label: string; cantidad: string; precio: string }[] = [
  { value: 'mano_obra', label: 'Mano de obra', cantidad: 'Horas', precio: 'Tarifa por hora (€)' },
  { value: 'recambio', label: 'Recambio', cantidad: 'Unidades', precio: 'Precio por unidad (€)' },
  { value: 'externo', label: 'Trabajo externo', cantidad: 'Cantidad', precio: 'Importe (€)' },
]
const ORIGEN = { plan: 'Plan preventivo', averia: 'Avería', manual: 'Manual' } as const
const fechaHora = (iso: string) => new Date(iso).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })

export default function OrdenTrabajo() {
  const id = Number(useParams().id)
  const orden = useOrden(id)
  const { usuario } = useSesion()

  if (orden.isPending) return <Cargando />
  if (orden.error) {
    const noExiste = orden.error instanceof ErrorApi && orden.error.status === 404
    return noExiste ? <Alert color="gray">Esta orden de trabajo no existe o no es de tu empresa.</Alert> : <ErrorCarga error={orden.error} />
  }

  const ot = orden.data
  const editable = ot.estado === 'abierta' || ot.estado === 'en_curso'
  const gestiona = puedeGestionarTaller(usuario)

  return (
    <Stack maw={960}>
      <Anchor component={Link} to="/taller" size="sm">
        <Group gap={4}>
          <IconArrowLeft size={16} /> Taller
        </Group>
      </Anchor>

      <Group justify="space-between" align="start">
        <div>
          <Group gap="sm">
            <Title order={2}>OT n.º {ot.id}</Title>
            <EstadoOT valor={ot.estado} />
            <TipoOrden valor={ot.tipo} />
          </Group>
          <Text c="dimmed">
            <Anchor component={Link} to={`/vehiculos/${ot.vehiculo_id}`} ff="monospace" fw={600}>
              {ot.matricula}
            </Anchor>{' '}
            · Vehículo <EstadoVehiculo valor={ot.estado_vehiculo} />
          </Text>
        </div>
        {gestiona && editable && <Acciones ot={ot} />}
      </Group>

      {ot.inmoviliza && editable && (
        <Alert color="orange" icon={<IconHandStop />}>
          Esta OT inmoviliza el vehículo: está "en taller" hasta que se cierre o se cancele.
        </Alert>
      )}

      <Card withBorder>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
          <Dato etiqueta="Descripción" valor={ot.descripcion} />
          <Dato
            etiqueta="Origen"
            valor={
              ot.origen === 'averia' ? (
                <Anchor component={Link} to="/averias">
                  Avería n.º {ot.averia_id}
                </Anchor>
              ) : ot.origen === 'plan' ? (
                `Plan: ${ot.plan_nombre}`
              ) : (
                ORIGEN[ot.origen]
              )
            }
          />
          <Dato etiqueta="Responsable" valor={ot.responsable_nombre ?? '—'} />
          <Dato etiqueta="Abierta" valor={fechaHora(ot.abierta_en)} />
          <Dato etiqueta="Iniciada" valor={ot.iniciada_en ? fechaHora(ot.iniciada_en) : '—'} />
          {ot.estado === 'cerrada' && (
            <Dato etiqueta="Cierre" valor={`${formatoFecha(ot.fecha_cierre!)} · ${formatoKm(ot.km_cierre!)}`} />
          )}
          {ot.trabajo_realizado && <Dato etiqueta="Trabajo realizado" valor={ot.trabajo_realizado} />}
          {ot.estado === 'cancelada' && <Dato etiqueta="Motivo de cancelación" valor={ot.motivo_cancelacion ?? '—'} />}
        </SimpleGrid>
      </Card>

      <Lineas ot={ot} editable={gestiona && editable} />
    </Stack>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {etiqueta}
      </Text>
      <Text component="div">{valor}</Text>
    </div>
  )
}

// --- Acciones del flujo (MAN-05) ---------------------------------------------

function Acciones({ ot }: { ot: OT }) {
  const accion = useAccionOT(ot.id)
  const vehiculo = useVehiculo(ot.vehiculo_id)
  const [cerrando, setCerrando] = useState(false)
  const [cancelando, setCancelando] = useState(false)
  const [km, setKm] = useState<number | string>('')
  const [fecha, setFecha] = useState(hoyIso())
  const [trabajo, setTrabajo] = useState('')
  const [motivo, setMotivo] = useState('')

  const ejecutar = (datos: Parameters<typeof accion.mutate>[0], mensaje: string, alTerminar?: () => void) =>
    accion.mutate(datos, {
      onSuccess: (r) => {
        notifications.show({ color: 'green', message: `${mensaje} · vehículo ${r.estado_vehiculo.replace('_', ' ')}` })
        alTerminar?.()
      },
      onError: (e) => notifications.show({ color: 'red', message: e.message }),
    })

  const abrirCierre = () => {
    setKm(vehiculo.data?.km_actuales ?? '') // propuesta: los km actuales; el taller los corrige si ha rodado
    setCerrando(true)
  }
  const cerrar = (evento: FormEvent) => {
    evento.preventDefault()
    ejecutar({ accion: 'cerrar', km: Number(km), fecha, trabajo_realizado: trabajo || undefined }, 'OT cerrada', () => setCerrando(false))
  }

  return (
    <Group gap="xs">
      {ot.estado === 'abierta' && (
        <Button leftSection={<IconPlayerPlay size={16} />} loading={accion.isPending} onClick={() => ejecutar({ accion: 'iniciar' }, 'OT en curso')}>
          Iniciar
        </Button>
      )}
      {ot.estado === 'en_curso' && (
        <Button color="green" onClick={abrirCierre}>
          Cerrar
        </Button>
      )}
      <Button variant="default" color="red" onClick={() => setCancelando(true)}>
        Cancelar OT
      </Button>

      <Modal opened={cerrando} onClose={() => setCerrando(false)} title={`Cerrar OT n.º ${ot.id}`} centered>
        <form onSubmit={cerrar}>
          <Stack>
            <Text size="sm" c="dimmed">
              MAN-05: al cerrar se exigen los km y la fecha. Los km quedan registrados como lectura del vehículo
              {ot.tipo === 'preventiva' && ' y el plan calculará el próximo mantenimiento a partir de ellos'}.
            </Text>
            <NumberInput label="Km del vehículo al cerrar" required min={0} thousandSeparator="." decimalSeparator="," allowDecimal={false} value={km} onChange={setKm} />
            <TextInput label="Fecha de cierre" type="date" required max={hoyIso()} value={fecha} onChange={(e) => setFecha(e.currentTarget.value)} />
            <Textarea label="Trabajo realizado (opcional)" autosize minRows={2} maxLength={2000} value={trabajo} onChange={(e) => setTrabajo(e.currentTarget.value)} />
            {accion.error && <Alert color="red">{accion.error.message}</Alert>}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setCerrando(false)}>
                Volver
              </Button>
              <Button type="submit" color="green" loading={accion.isPending}>
                Cerrar OT
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal opened={cancelando} onClose={() => setCancelando(false)} title={`Cancelar OT n.º ${ot.id}`} centered>
        <Stack>
          <Text size="sm">
            La OT quedará cancelada (no se borra).
            {ot.origen === 'averia' && ' La avería volverá a "comunicada": sigue sin reparar.'}
          </Text>
          <Textarea label="Motivo (opcional)" autosize minRows={2} value={motivo} onChange={(e) => setMotivo(e.currentTarget.value)} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCancelando(false)}>
              Volver
            </Button>
            <Button color="red" loading={accion.isPending} onClick={() => ejecutar({ accion: 'cancelar', motivo: motivo || undefined }, 'OT cancelada', () => setCancelando(false))}>
              Cancelar OT
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Group>
  )
}

// --- Líneas de coste (MAN-06) ------------------------------------------------

function Lineas({ ot, editable }: { ot: OT; editable: boolean }) {
  const borrar = useBorrarLinea(ot.id)
  const c = ot.coste
  return (
    <Card withBorder padding={0}>
      <Group justify="space-between" p="md" pb={0}>
        <Title order={3} size="h4">
          Coste
        </Title>
        <Text fw={700} fz="lg">
          {formatoEuros(c.total)}
        </Text>
      </Group>
      <Text size="sm" c="dimmed" px="md">
        Mano de obra {formatoEuros(c.mano_obra)} · Recambios {formatoEuros(c.recambios)} · Externos {formatoEuros(c.externos)}
      </Text>
      <Table.ScrollContainer minWidth={600}>
        <Table striped mt="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Concepto</Table.Th>
              <Table.Th>Descripción</Table.Th>
              <Table.Th ta="right">Cantidad</Table.Th>
              <Table.Th ta="right">Precio</Table.Th>
              <Table.Th ta="right">Importe</Table.Th>
              {editable && <Table.Th />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {ot.lineas.map((l) => (
              <Table.Tr key={l.id}>
                <Table.Td>{CONCEPTOS.find((c) => c.value === l.concepto)?.label}</Table.Td>
                <Table.Td>{l.descripcion}</Table.Td>
                <Table.Td ta="right">{l.cantidad.toLocaleString('es-ES')}</Table.Td>
                <Table.Td ta="right">{formatoEuros(l.precio_unitario)}</Table.Td>
                <Table.Td ta="right">{formatoEuros(l.importe)}</Table.Td>
                {editable && (
                  <Table.Td>
                    <Tooltip label="Quitar línea">
                      <ActionIcon variant="subtle" color="red" aria-label={`Quitar ${l.descripcion}`} loading={borrar.isPending} onClick={() => borrar.mutate(l.id)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
            {ot.lineas.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={6}>
                  <Text c="dimmed" ta="center" py="sm">
                    Sin líneas de coste todavía.
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {editable && <NuevaLinea otId={ot.id} />}
    </Card>
  )
}

function NuevaLinea({ otId }: { otId: number }) {
  const anadir = useAnadirLinea(otId)
  const [concepto, setConcepto] = useState<Concepto>('mano_obra')
  const [descripcion, setDescripcion] = useState('')
  const [cantidad, setCantidad] = useState<number | string>(1)
  const [precio, setPrecio] = useState<number | string>('')
  const [recambioId, setRecambioId] = useState<string | null>(null)
  const etiquetas = CONCEPTOS.find((c) => c.value === concepto)!
  const recambios = useRecambios()

  // MAN-09: al elegir un recambio del catálogo se rellenan la descripción y su precio por defecto
  // (se pueden cambiar antes de añadir la línea).
  const elegirRecambio = (id: string | null) => {
    setRecambioId(id)
    const recambio = recambios.data?.find((r) => String(r.id) === id)
    if (recambio) {
      setDescripcion(`${recambio.nombre} (${recambio.referencia})`)
      setPrecio(recambio.precio)
    }
  }

  const cambiarConcepto = (valor: Concepto) => {
    setConcepto(valor)
    if (valor !== 'recambio') setRecambioId(null) // el catálogo solo vale para recambios
  }

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    anadir.mutate(
      { concepto, recambio_id: recambioId ? Number(recambioId) : null, descripcion, cantidad: Number(cantidad), precio_unitario: Number(precio) },
      {
        onSuccess: () => {
          setDescripcion('')
          setCantidad(1)
          setPrecio('')
          setRecambioId(null)
        },
      },
    )
  }

  return (
    <form onSubmit={enviar}>
      <Group align="end" gap="sm" p="md">
        <Select label="Concepto" data={CONCEPTOS} value={concepto} onChange={(v) => cambiarConcepto((v ?? 'mano_obra') as Concepto)} allowDeselect={false} w={150} />
        {concepto === 'recambio' && (
          <Select
            label="Del catálogo"
            placeholder="Buscar referencia o nombre"
            searchable
            clearable
            nothingFoundMessage="No está en el catálogo"
            data={recambios.data?.map((r) => ({ value: String(r.id), label: `${r.referencia} · ${r.nombre} · ${formatoEuros(r.precio)}` })) ?? []}
            value={recambioId}
            onChange={elegirRecambio}
            w={{ base: '100%', sm: 300 }}
          />
        )}
        <TextInput label="Descripción" required maxLength={200} value={descripcion} onChange={(e) => setDescripcion(e.currentTarget.value)} style={{ flex: 1, minWidth: 180 }} />
        <NumberInput label={etiquetas.cantidad} required min={0.01} decimalScale={2} decimalSeparator="," value={cantidad} onChange={setCantidad} w={110} />
        <NumberInput label={etiquetas.precio} required min={0} decimalScale={2} decimalSeparator="," value={precio} onChange={setPrecio} w={160} />
        <Button type="submit" loading={anadir.isPending}>
          Añadir
        </Button>
      </Group>
      {anadir.error && (
        <Alert color="red" mx="md" mb="md">
          {anadir.error.message}
        </Alert>
      )}
    </form>
  )
}
