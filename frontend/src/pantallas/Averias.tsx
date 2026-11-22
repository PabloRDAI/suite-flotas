// Listado de averías (MAN-03) para el taller: abiertas por defecto, con su foto
// y la opción de resolverlas (gerente y taller).

import {
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Image,
  Loader,
  Modal,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCircleCheck, IconClipboardList, IconPhoto, IconPlus } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAverias, useCrearOT, useFotoAveria, useResolverAveria } from '../api/consultas.ts'
import type { Averia, EstadoAveria, Gravedad } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarTaller } from '../auth/permisos.ts'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { EstadoVehiculo } from '../componentes/Indicadores.tsx'

const GRAVEDAD: Record<Gravedad, { color: string; texto: string }> = {
  inmoviliza: { color: 'red', texto: 'Inmoviliza' },
  grave: { color: 'orange', texto: 'Grave' },
  leve: { color: 'blue', texto: 'Leve' },
}
const ESTADO: Record<EstadoAveria, { color: string; texto: string }> = {
  comunicada: { color: 'yellow', texto: 'Comunicada' },
  en_reparacion: { color: 'indigo', texto: 'En reparación' },
  resuelta: { color: 'green', texto: 'Resuelta' },
}

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function Averias() {
  const { usuario } = useSesion()
  const [vista, setVista] = useState<'abiertas' | 'todas'>('abiertas')
  const [gravedad, setGravedad] = useState<string | null>(null)
  const averias = useAverias(vista === 'abiertas', gravedad)

  return (
    <Stack>
      <Group justify="space-between" align="end">
        <Title order={2}>Averías</Title>
        <Button component={Link} to="/averias/nueva" color="red" leftSection={<IconPlus size={16} />}>
          Comunicar avería
        </Button>
      </Group>
      <Group align="end" gap="sm">
        <SegmentedControl
          value={vista}
          onChange={(v) => setVista(v as 'abiertas' | 'todas')}
          data={[
            { value: 'abiertas', label: 'Abiertas' },
            { value: 'todas', label: 'Todas' },
          ]}
        />
        <Select
          placeholder="Cualquier gravedad"
          clearable
          data={Object.entries(GRAVEDAD).map(([value, { texto }]) => ({ value, label: texto }))}
          value={gravedad}
          onChange={setGravedad}
          w={200}
          aria-label="Gravedad"
        />
      </Group>

      {averias.isPending && <Cargando />}
      {averias.error && <ErrorCarga error={averias.error} />}
      {averias.data?.length === 0 && (
        <Group gap="xs" c="green">
          <IconCircleCheck size={18} aria-hidden />
          <Text>{vista === 'abiertas' ? 'No hay averías abiertas.' : 'No hay averías registradas.'}</Text>
        </Group>
      )}
      {/* Tarjetas en lugar de tabla: se leen bien también en el móvil. */}
      {averias.data?.map((a) => (
        <TarjetaAveria key={a.id} averia={a} puedeResolver={puedeGestionarTaller(usuario)} />
      ))}
    </Stack>
  )
}

function TarjetaAveria({ averia: a, puedeResolver }: { averia: Averia; puedeResolver: boolean }) {
  const [verFoto, setVerFoto] = useState(false)
  const [resolviendo, setResolviendo] = useState(false)
  const crearOT = useCrearOT()
  const navegar = useNavigate()
  // MAN-04: la OT se crea desde la avería (queda enlazada y "en reparación") y se abre su ficha.
  const crear = () =>
    crearOT.mutate(
      { averia_id: a.id },
      {
        onSuccess: (ot) => void navegar(`/ordenes-trabajo/${ot.id}`),
        onError: (e) => notifications.show({ color: 'red', message: e.message }),
      },
    )
  return (
    <Card withBorder>
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap" align="start">
          <Group gap="xs">
            <Anchor component={Link} to={`/vehiculos/${a.vehiculo_id}`} ff="monospace" fw={700}>
              {a.matricula}
            </Anchor>
            <Badge color={GRAVEDAD[a.gravedad].color}>{GRAVEDAD[a.gravedad].texto}</Badge>
            <Badge color={ESTADO[a.estado].color} variant="light">
              {ESTADO[a.estado].texto}
            </Badge>
          </Group>
          <EstadoVehiculo valor={a.estado_vehiculo} />
        </Group>
        <Text>{a.descripcion}</Text>
        <Text size="xs" c="dimmed">
          {fechaHora(a.comunicada_en)} · {a.comunicada_por ?? 'Usuario eliminado'}
          {a.resuelta_en && ` · Resuelta el ${fechaHora(a.resuelta_en)}${a.nota_resolucion ? `: ${a.nota_resolucion}` : ''}`}
        </Text>
        <Group gap="xs">
          {a.tiene_foto && (
            <Button size="xs" variant="default" leftSection={<IconPhoto size={14} />} onClick={() => setVerFoto(true)}>
              Ver foto
            </Button>
          )}
          {a.orden_trabajo_id !== null && (
            <Button size="xs" variant="default" leftSection={<IconClipboardList size={14} />} component={Link} to={`/ordenes-trabajo/${a.orden_trabajo_id}`}>
              Ver OT
            </Button>
          )}
          {puedeResolver && a.estado === 'comunicada' && (
            <Button size="xs" loading={crearOT.isPending} onClick={crear}>
              Crear OT
            </Button>
          )}
          {puedeResolver && a.estado === 'comunicada' && (
            <Button size="xs" variant="light" color="green" onClick={() => setResolviendo(true)}>
              Resolver sin OT
            </Button>
          )}
        </Group>
      </Stack>
      <Modal opened={verFoto} onClose={() => setVerFoto(false)} title={`Foto · ${a.matricula}`} size="lg" centered>
        <Foto averiaId={a.id} activa={verFoto} />
      </Modal>
      <ModalResolver averia={a} abierto={resolviendo} cerrar={() => setResolviendo(false)} />
    </Card>
  )
}

function Foto({ averiaId, activa }: { averiaId: number; activa: boolean }) {
  const foto = useFotoAveria(averiaId, activa)
  if (foto.isPending) return <Center py="xl"><Loader /></Center>
  if (foto.error) return <Text c="red">No se ha podido cargar la foto.</Text>
  return <Image src={foto.data} alt="Foto de la avería" radius="sm" />
}

function ModalResolver({ averia, abierto, cerrar }: { averia: Averia; abierto: boolean; cerrar: () => void }) {
  const [nota, setNota] = useState('')
  const resolver = useResolverAveria()
  const confirmar = () =>
    resolver.mutate(
      { id: averia.id, nota },
      {
        onSuccess: (r) => {
          notifications.show({
            color: 'green',
            message:
              r.estado_vehiculo === 'operativo'
                ? `Avería resuelta: ${r.matricula} vuelve a estar operativo`
                : `Avería resuelta (${r.matricula} sigue ${r.estado_vehiculo.replace('_', ' ')})`,
          })
          cerrar()
        },
        onError: (e) => notifications.show({ color: 'red', message: e.message }),
      },
    )
  return (
    <Modal opened={abierto} onClose={cerrar} title={`Resolver avería · ${averia.matricula}`} centered>
      <Stack>
        <Text size="sm">{averia.descripcion}</Text>
        <Textarea label="Nota (opcional)" placeholder="Qué se ha hecho" value={nota} onChange={(e) => setNota(e.currentTarget.value)} autosize minRows={2} maxLength={1000} />
        <Group justify="flex-end">
          <Button variant="default" onClick={cerrar}>
            Cancelar
          </Button>
          <Button color="green" loading={resolver.isPending} onClick={confirmar}>
            Marcar como resuelta
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
