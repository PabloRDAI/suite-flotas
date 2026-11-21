// Estado del sistema: comprueba que la API y la base de datos responden (GET /salud).

import { Alert, Button, Card, Group, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconCircleCheck, IconCircleX, IconLoader } from '@tabler/icons-react'
import { comprobarSalud } from '../api/salud.ts'

type Estado = 'ok' | 'error' | 'comprobando' | 'desconocido'

function Fila({ nombre, estado, texto }: { nombre: string; estado: Estado; texto: string }) {
  const color = { ok: 'green', error: 'red', comprobando: 'gray', desconocido: 'gray' }[estado]
  const Icono = { ok: IconCircleCheck, error: IconCircleX, comprobando: IconLoader, desconocido: IconLoader }[estado]
  return (
    <Group justify="space-between">
      <Text fw={600}>{nombre}</Text>
      <Group gap={6} c={color}>
        <Icono size={18} aria-hidden />
        <Text>{texto}</Text>
      </Group>
    </Group>
  )
}

export default function EstadoSistema() {
  const salud = useQuery({ queryKey: ['salud'], queryFn: () => comprobarSalud(), staleTime: 0 })
  const r = salud.data
  const comprobando = salud.isFetching

  let api: [Estado, string] = ['comprobando', 'Comprobando…']
  let bd: [Estado, string] = ['comprobando', 'Comprobando…']
  if (!comprobando && r) {
    api = r.tipo === 'api_caida' ? ['error', 'Sin respuesta'] : ['ok', 'Conectada']
    bd = r.tipo === 'ok' ? ['ok', 'Conectada'] : r.tipo === 'bd_caida' ? ['error', 'Sin conexión'] : ['desconocido', 'Desconocido']
  }

  return (
    <Stack maw={520}>
      <Title order={2}>Estado del sistema</Title>
      <Card withBorder>
        <Stack>
          <Fila nombre="API" estado={api[0]} texto={api[1]} />
          <Fila nombre="Base de datos" estado={bd[0]} texto={bd[1]} />
          {!comprobando && r?.tipo === 'api_caida' && (
            <Alert color="red" role="alert">
              {r.mensaje}
            </Alert>
          )}
          <Group>
            <Button variant="default" onClick={() => void salud.refetch()} loading={comprobando}>
              Volver a comprobar
            </Button>
            {salud.dataUpdatedAt > 0 && (
              <Text size="sm" c="dimmed">
                Última comprobación: {new Date(salud.dataUpdatedAt).toLocaleTimeString('es-ES')}
              </Text>
            )}
          </Group>
        </Stack>
      </Card>
    </Stack>
  )
}
