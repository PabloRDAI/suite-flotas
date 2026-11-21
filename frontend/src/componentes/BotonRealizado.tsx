// Botón "Registrar realizado" de un preventivo, con confirmación (MAN-01).
// Registra que el mantenimiento se ha hecho HOY con los km actuales del vehículo.
// (Más adelante lo hará solo el cierre de una orden de trabajo preventiva, MAN-05.)

import { Button, Group, List, Modal, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck } from '@tabler/icons-react'
import { useState } from 'react'
import { useRegistrarRealizacion } from '../api/consultas.ts'
import { formatoKm } from '../util/formato.ts'

type Props = {
  vehiculoId: number
  matricula: string
  planId: number
  planNombre: string
  kmActuales: number
  tareas: string[]
}

export function BotonRealizado({ vehiculoId, matricula, planId, planNombre, kmActuales, tareas }: Props) {
  const [abierto, setAbierto] = useState(false)
  const registrar = useRegistrarRealizacion()

  const confirmar = () =>
    registrar.mutate(
      { vehiculoId, planId },
      {
        onSuccess: () => notifications.show({ color: 'green', message: `${planNombre} de ${matricula} registrado como hecho hoy` }),
        onError: (e) => notifications.show({ color: 'red', message: e.message }),
        onSettled: () => setAbierto(false),
      },
    )

  return (
    <>
      <Button size="xs" variant="light" leftSection={<IconCheck size={14} />} onClick={() => setAbierto(true)}>
        Registrar realizado
      </Button>
      <Modal opened={abierto} onClose={() => setAbierto(false)} title="Registrar mantenimiento realizado" centered>
        <Stack>
          <Text>
            ¿Se ha hecho hoy <b>{planNombre}</b> a <b>{matricula}</b> con {formatoKm(kmActuales)}?
          </Text>
          {tareas.length > 0 && (
            <>
              <Text size="sm" c="dimmed">
                Tareas del plan:
              </Text>
              <List size="sm">
                {tareas.map((t) => (
                  <List.Item key={t}>{t}</List.Item>
                ))}
              </List>
            </>
          )}
          <Text size="sm" c="dimmed">
            El próximo se calculará a partir de hoy y de estos km.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setAbierto(false)}>
              Cancelar
            </Button>
            <Button loading={registrar.isPending} onClick={confirmar}>
              Registrar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
