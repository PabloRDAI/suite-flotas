// Estados comunes de una pantalla mientras llegan los datos: cargando o error.

import { Alert, Center, Loader } from '@mantine/core'
import { IconAlertCircle } from '@tabler/icons-react'

export function Cargando() {
  return (
    <Center py="xl">
      <Loader aria-label="Cargando" />
    </Center>
  )
}

export function ErrorCarga({ error }: { error: Error }) {
  return (
    <Alert color="red" icon={<IconAlertCircle />} title="No se han podido cargar los datos" role="alert">
      {error.message}
    </Alert>
  )
}
