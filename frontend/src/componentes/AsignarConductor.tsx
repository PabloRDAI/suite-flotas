// Formulario "Asignar conductor/a" de la ficha del vehículo (PER-03, PER-04).
//
// - Si el vehículo ya tiene habitual, ofrece finalizar esa asignación en el mismo paso
//   (si no, la API respondería 409: solo un habitual a la vez).
// - Muestra el semáforo de cada conductor al elegir y avisa ANTES si su documentación
//   está caducada. La asignación se hace igualmente (PER-04: avisa, no bloquea).

import { Alert, Button, Card, Checkbox, Group, SegmentedControl, Select, Stack, Text, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle } from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { useAsignar, usePersonas } from '../api/consultas.ts'
import type { Asignacion, Persona } from '../api/tipos.ts'
import { formatoFecha, hoyIso } from '../util/formato.ts'
import { IndicadorSemaforo } from './Indicadores.tsx'

type Props = {
  vehiculoId: number
  /** Asignaciones del vehículo, para saber si ya tiene un habitual en vigor. */
  asignaciones: Asignacion[]
}

export function AsignarConductor({ vehiculoId, asignaciones }: Props) {
  const personas = usePersonas(false)
  const asignar = useAsignar()

  const [personaId, setPersonaId] = useState<string | null>(null)
  const [tipo, setTipo] = useState<'habitual' | 'temporal'>('habitual')
  const [desde, setDesde] = useState(hoyIso())
  const [hasta, setHasta] = useState('')
  const [finalizarActual, setFinalizarActual] = useState(true)

  const conductores = (personas.data ?? []).filter((p) => p.puesto === 'conductor')
  const porId = new Map(conductores.map((p) => [String(p.id), p]))
  const elegida: Persona | undefined = personaId ? porId.get(personaId) : undefined
  const habitualActual = asignaciones.find((a) => a.vigente && a.habitual && !a.hasta)
  const habitual = tipo === 'habitual'

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    if (!elegida) return
    asignar.mutate(
      {
        persona_id: elegida.id,
        vehiculo_id: vehiculoId,
        desde,
        hasta: habitual ? undefined : hasta,
        habitual,
        finalizarAntes: habitual && habitualActual && finalizarActual ? habitualActual.id : undefined,
      },
      {
        onSuccess: (nueva) => {
          notifications.show({ color: 'green', message: `${nueva.persona_nombre} asignado/a a ${nueva.matricula}` })
          // PER-04: la asignación se ha hecho, pero hay que avisar (y que no desaparezca solo).
          if (nueva.avisos.length > 0) {
            notifications.show({
              color: 'yellow',
              title: `Documentación caducada de ${nueva.persona_nombre}`,
              message: nueva.avisos.join(' · '),
              autoClose: false,
            })
          }
          setPersonaId(null)
          setHasta('')
        },
      },
    )
  }

  return (
    <Card withBorder>
      <form onSubmit={enviar}>
        <Stack>
          <Title order={3} size="h5">
            Asignar conductor/a
          </Title>

          <Group align="end" gap="sm">
            <Select
              label="Conductor/a"
              placeholder="Buscar por nombre"
              searchable
              required
              nothingFoundMessage="No hay conductores con ese nombre"
              data={conductores.map((p) => ({ value: String(p.id), label: p.nombre }))}
              // Cada opción muestra el semáforo de su documentación (PER-02).
              renderOption={({ option }) => {
                const p = porId.get(option.value)
                return (
                  <Group justify="space-between" w="100%" wrap="nowrap">
                    <Text size="sm">{option.label}</Text>
                    {p && p.semaforo !== 'verde' && <IndicadorSemaforo valor={p.semaforo} />}
                  </Group>
                )
              }}
              value={personaId}
              onChange={setPersonaId}
              w={{ base: '100%', sm: 280 }}
            />
            <SegmentedControl
              value={tipo}
              onChange={(v) => setTipo(v as 'habitual' | 'temporal')}
              data={[
                { value: 'habitual', label: 'Habitual' },
                { value: 'temporal', label: 'Temporal' },
              ]}
              aria-label="Tipo de asignación"
            />
            <TextInput label="Desde" type="date" required value={desde} onChange={(e) => setDesde(e.currentTarget.value)} w={170} />
            {!habitual && (
              <TextInput
                label="Hasta"
                type="date"
                required // una sustitución siempre tiene fin
                min={desde}
                value={hasta}
                onChange={(e) => setHasta(e.currentTarget.value)}
                w={170}
              />
            )}
          </Group>

          {habitual && habitualActual && (
            <Checkbox
              checked={finalizarActual}
              onChange={(e) => setFinalizarActual(e.currentTarget.checked)}
              label={`Finalizar la asignación actual de ${habitualActual.persona_nombre} (desde el ${formatoFecha(habitualActual.desde)}; terminará ayer)`}
              description="Un vehículo solo puede tener un conductor/a habitual a la vez. La asignación anterior se conserva en el historial."
            />
          )}

          {elegida?.semaforo === 'rojo' && (
            <Alert color="yellow" icon={<IconAlertTriangle />} title="Documentación caducada">
              {elegida.nombre} tiene documentación caducada. Puedes asignarle igualmente, pero quedará el aviso.
            </Alert>
          )}

          {asignar.error && (
            <Alert color="red" role="alert">
              {asignar.error.message}
            </Alert>
          )}

          <Group>
            <Button type="submit" loading={asignar.isPending} disabled={!elegida}>
              Asignar
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  )
}
