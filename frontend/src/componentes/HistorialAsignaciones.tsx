// Historial de asignaciones (PER-03) con sus avisos (PER-04).
// Desde un vehículo se ve la columna "Conductor/a"; desde una persona, "Vehículo".

import { Anchor, Badge, Button, Group, List, Modal, Stack, Table, Text, ThemeIcon } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle } from '@tabler/icons-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useFinalizarAsignacion } from '../api/consultas.ts'
import type { Asignacion } from '../api/tipos.ts'
import { formatoFecha, hoyIso } from '../util/formato.ts'

type Props = {
  asignaciones: Asignacion[]
  mostrar: 'conductor' | 'vehiculo'
  puedeFinalizar: boolean
}

export function HistorialAsignaciones({ asignaciones, mostrar, puedeFinalizar }: Props) {
  const [aFinalizar, setAFinalizar] = useState<Asignacion | null>(null)
  const finalizar = useFinalizarAsignacion()

  if (asignaciones.length === 0) return <Text c="dimmed">Sin asignaciones registradas.</Text>

  const confirmar = () => {
    if (!aFinalizar) return
    finalizar.mutate(aFinalizar.id, {
      onSuccess: (a) =>
        notifications.show({ color: 'green', message: `Asignación de ${a.persona_nombre} finalizada el ${formatoFecha(a.hasta!)}` }),
      onError: (e) => notifications.show({ color: 'red', message: e.message }),
      onSettled: () => setAFinalizar(null),
    })
  }

  return (
    <>
      <Table.ScrollContainer minWidth={640}>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{mostrar === 'conductor' ? 'Conductor/a' : 'Vehículo'}</Table.Th>
              <Table.Th>Tipo</Table.Th>
              <Table.Th>Desde</Table.Th>
              <Table.Th>Hasta</Table.Th>
              <Table.Th>Situación</Table.Th>
              {puedeFinalizar && <Table.Th />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {asignaciones.map((a) => (
              <Table.Tr key={a.id} c={situacion(a) === 'terminada' ? 'dimmed' : undefined}>
                <Table.Td>
                  {mostrar === 'conductor' ? (
                    <Anchor component={Link} to={`/personal/${a.persona_id}`}>
                      {a.persona_nombre}
                    </Anchor>
                  ) : (
                    <Anchor component={Link} to={`/vehiculos/${a.vehiculo_id}`} ff="monospace" fw={600}>
                      {a.matricula}
                    </Anchor>
                  )}
                  {/* PER-04: avisos de documentación caducada, con icono y texto. */}
                  {a.avisos.length > 0 && (
                    <Group gap={4} mt={4} wrap="nowrap" c="yellow.7">
                      <ThemeIcon size="xs" color="yellow" variant="light" aria-hidden>
                        <IconAlertTriangle size={12} />
                      </ThemeIcon>
                      <Text size="xs">{a.avisos.join(' · ')}</Text>
                    </Group>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={a.habitual ? 'indigo' : 'gray'}>
                    {a.habitual ? 'Habitual' : 'Temporal'}
                  </Badge>
                </Table.Td>
                <Table.Td>{formatoFecha(a.desde)}</Table.Td>
                <Table.Td>{a.hasta ? formatoFecha(a.hasta) : '—'}</Table.Td>
                <Table.Td>
                  <Situacion a={a} />
                </Table.Td>
                {puedeFinalizar && (
                  <Table.Td>
                    {!a.hasta && (
                      <Button size="xs" variant="default" onClick={() => setAFinalizar(a)}>
                        Finalizar
                      </Button>
                    )}
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {/* Confirmación antes de cambiar datos. */}
      <Modal opened={aFinalizar !== null} onClose={() => setAFinalizar(null)} title="Finalizar asignación" centered>
        {aFinalizar && (
          <Stack>
            <Text>
              ¿Finalizar la asignación de <b>{aFinalizar.persona_nombre}</b> al vehículo <b>{aFinalizar.matricula}</b>?
            </Text>
            <List size="sm" c="dimmed">
              <List.Item>Terminará ayer (o hoy, si empezó hoy), para que otra persona pueda empezar hoy.</List.Item>
              <List.Item>No se borra: queda en el historial.</List.Item>
            </List>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setAFinalizar(null)}>
                Cancelar
              </Button>
              <Button color="red" loading={finalizar.isPending} onClick={confirmar}>
                Finalizar
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </>
  )
}

type EstadoAsignacion = 'en_vigor' | 'programada' | 'terminada'

/** En vigor hoy, programada (empieza en el futuro) o terminada. Fechas "AAAA-MM-DD"
 *  comparadas como texto: en ese formato el orden alfabético es el cronológico. */
function situacion(a: Asignacion): EstadoAsignacion {
  if (a.vigente) return 'en_vigor'
  return a.desde > hoyIso() ? 'programada' : 'terminada'
}

const SITUACION = {
  en_vigor: { color: 'green', texto: 'En vigor' },
  programada: { color: 'blue', texto: 'Programada' },
  terminada: { color: 'gray', texto: 'Terminada' },
} as const

function Situacion({ a }: { a: Asignacion }) {
  const { color, texto } = SITUACION[situacion(a)]
  return (
    <Badge color={color} variant="light">
      {texto}
    </Badge>
  )
}
