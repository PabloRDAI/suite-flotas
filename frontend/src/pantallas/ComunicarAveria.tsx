// Comunicar una avería (MAN-03), pensada para el MÓVIL y para hacerse en menos de un minuto:
// - vehículo preseleccionado (el asignado al conductor),
// - gravedad con tres botones grandes (no un desplegable),
// - foto con la cámara del móvil directamente,
// - y una confirmación clara de lo que ha pasado con el vehículo.

import {
  Alert,
  Button,
  Card,
  CloseButton,
  FileButton,
  Group,
  Image,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { IconAlertTriangle, IconCamera, IconCircleCheck, IconHandStop, IconInfoCircle } from '@tabler/icons-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { useComunicarAveria, useVehiculos, useVehiculosSugeridos } from '../api/consultas.ts'
import type { Averia, Gravedad } from '../api/tipos.ts'

const GRAVEDADES: { valor: Gravedad; titulo: string; ayuda: string; color: string; Icono: typeof IconInfoCircle }[] = [
  { valor: 'leve', titulo: 'Leve', ayuda: 'Puede seguir circulando', color: 'blue', Icono: IconInfoCircle },
  { valor: 'grave', titulo: 'Grave', ayuda: 'Hay que revisarlo pronto', color: 'orange', Icono: IconAlertTriangle },
  { valor: 'inmoviliza', titulo: 'Inmoviliza', ayuda: 'No puede circular', color: 'red', Icono: IconHandStop },
]

export default function ComunicarAveria() {
  const sugeridos = useVehiculosSugeridos()
  const vehiculos = useVehiculos(false)
  const comunicar = useComunicarAveria()

  const [vehiculoId, setVehiculoId] = useState<string | null>(null)
  const [gravedad, setGravedad] = useState<Gravedad | null>(null)
  const [descripcion, setDescripcion] = useState('')
  const [foto, setFoto] = useState<File | null>(null)
  const [hecha, setHecha] = useState<Averia | null>(null)

  // Preseleccionar el vehículo asignado (el habitual sale primero).
  const sugerido = sugeridos.data?.[0]
  const elegido = vehiculoId ?? (sugerido ? String(sugerido.id) : null)

  // Opciones: primero los asignados al usuario, después el resto de la flota.
  const opciones = useMemo(() => {
    const propios = new Set(sugeridos.data?.map((v) => v.id))
    const formato = (v: { id: number; matricula: string; marca: string; modelo: string }) => ({
      value: String(v.id),
      label: `${v.matricula} · ${v.marca} ${v.modelo}`,
    })
    return [
      { group: 'Asignados a ti', items: (sugeridos.data ?? []).map(formato) },
      { group: 'Resto de la flota', items: (vehiculos.data ?? []).filter((v) => !propios.has(v.id)).map(formato) },
    ].filter((g) => g.items.length > 0)
  }, [sugeridos.data, vehiculos.data])

  // Vista previa de la foto (y liberar la memoria al cambiarla o salir).
  const vistaPrevia = useMemo(() => (foto ? URL.createObjectURL(foto) : null), [foto])
  useEffect(() => () => (vistaPrevia ? URL.revokeObjectURL(vistaPrevia) : undefined), [vistaPrevia])

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    if (!elegido || !gravedad) return
    comunicar.mutate(
      { vehiculoId: Number(elegido), descripcion, gravedad, foto },
      { onSuccess: (averia) => setHecha(averia) },
    )
  }

  const empezarDeNuevo = () => {
    setHecha(null)
    setGravedad(null)
    setDescripcion('')
    setFoto(null)
    comunicar.reset()
  }

  if (hecha) return <Confirmacion averia={hecha} otra={empezarDeNuevo} />

  return (
    <Stack maw={560} mx="auto">
      <Title order={2}>Comunicar avería</Title>
      <form onSubmit={enviar}>
        <Stack gap="lg">
          <Select
            label="Vehículo"
            size="lg"
            searchable
            required
            placeholder="Busca por matrícula"
            data={opciones}
            value={elegido}
            onChange={setVehiculoId}
            nothingFoundMessage="Ningún vehículo con esa matrícula"
          />

          <div>
            <Text fw={500} mb={6}>
              Gravedad <Text span c="red">*</Text>
            </Text>
            {/* Tres botones grandes: fáciles de pulsar con el dedo y con el significado escrito. */}
            <SimpleGrid cols={3} spacing="xs" role="radiogroup" aria-label="Gravedad">
              {GRAVEDADES.map(({ valor, titulo, ayuda, color, Icono }) => {
                const activa = gravedad === valor
                return (
                  <UnstyledButton key={valor} onClick={() => setGravedad(valor)} role="radio" aria-checked={activa}>
                    <Card
                      withBorder
                      padding="sm"
                      h="100%"
                      bg={activa ? `var(--mantine-color-${color}-light)` : undefined}
                      style={{ borderColor: activa ? `var(--mantine-color-${color}-6)` : undefined, borderWidth: activa ? 2 : 1 }}
                    >
                      <Stack gap={4} align="center" ta="center">
                        <Icono size={28} color={`var(--mantine-color-${color}-6)`} aria-hidden />
                        <Text fw={700}>{titulo}</Text>
                        <Text size="xs" c="dimmed">
                          {ayuda}
                        </Text>
                      </Stack>
                    </Card>
                  </UnstyledButton>
                )
              })}
            </SimpleGrid>
          </div>

          <Textarea
            label="¿Qué le pasa?"
            size="lg"
            required
            minLength={3}
            maxLength={2000}
            autosize
            minRows={3}
            placeholder="Ej.: no arranca, ruido al frenar, pierde aceite…"
            value={descripcion}
            onChange={(e) => setDescripcion(e.currentTarget.value)}
          />

          <div>
            <Text fw={500} mb={6}>
              Foto (opcional)
            </Text>
            {vistaPrevia ? (
              <Group align="start" gap="xs">
                <Image src={vistaPrevia} alt="Vista previa de la foto" h={120} w="auto" radius="sm" />
                <CloseButton aria-label="Quitar la foto" onClick={() => setFoto(null)} />
              </Group>
            ) : (
              // capture="environment": en el móvil abre directamente la cámara trasera.
              <FileButton onChange={setFoto} accept="image/jpeg,image/png,image/webp" capture="environment">
                {(props) => (
                  <Button {...props} variant="default" size="lg" leftSection={<IconCamera />} fullWidth>
                    Hacer o elegir foto
                  </Button>
                )}
              </FileButton>
            )}
          </div>

          {comunicar.error && (
            <Alert color="red" role="alert">
              {comunicar.error.message}
            </Alert>
          )}

          <Button type="submit" size="xl" color="red" loading={comunicar.isPending} disabled={!elegido || !gravedad}>
            Comunicar avería
          </Button>
        </Stack>
      </form>
    </Stack>
  )
}

/** Qué ha pasado: la avería registrada y, sobre todo, cómo queda el vehículo. */
function Confirmacion({ averia, otra }: { averia: Averia; otra: () => void }) {
  return (
    <Stack maw={560} mx="auto">
      <Alert color="green" icon={<IconCircleCheck />} title="Avería comunicada">
        El taller ya puede verla. Vehículo <b>{averia.matricula}</b>.
      </Alert>
      {averia.estado_vehiculo === 'inmovilizado' && (
        <Alert color="red" icon={<IconHandStop />} title="El vehículo queda inmovilizado">
          No debe circular hasta que el taller lo revise.
        </Alert>
      )}
      <Button size="lg" onClick={otra}>
        Comunicar otra avería
      </Button>
      <Button size="lg" variant="default" component={Link} to="/averias">
        Ver averías
      </Button>
    </Stack>
  )
}
