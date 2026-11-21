// Ficha de una persona: aviso de documentación y pestañas de datos,
// documentación (PER-02) y asignaciones a vehículos (PER-03).

import { Alert, Anchor, Badge, Group, SimpleGrid, Stack, Tabs, Text, Title } from '@mantine/core'
import { IconAlertTriangle, IconArrowLeft, IconCircleX, IconFileCertificate, IconInfoCircle, IconSteeringWheel } from '@tabler/icons-react'
import { Link, useParams } from 'react-router'
import { ErrorApi } from '../api/cliente.ts'
import { useAsignacionesPersona, useCentros, usePersona, useVencimientosPersona } from '../api/consultas.ts'
import type { Persona } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarFlota } from '../auth/permisos.ts'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { Documentacion } from '../componentes/Documentacion.tsx'
import { HistorialAsignaciones } from '../componentes/HistorialAsignaciones.tsx'
import { formatoFecha, nombresPuesto } from '../util/formato.ts'

export default function FichaPersona() {
  const id = Number(useParams().id)
  const persona = usePersona(id)
  const vencimientos = useVencimientosPersona(id)
  const asignaciones = useAsignacionesPersona(id)
  const { usuario } = useSesion()

  if (persona.isPending) return <Cargando />
  if (persona.error) {
    const noExiste = persona.error instanceof ErrorApi && persona.error.status === 404
    return (
      <Stack>
        <VolverAlListado />
        {noExiste ? <Alert color="gray">Esta persona no existe o no es de tu empresa.</Alert> : <ErrorCarga error={persona.error} />}
      </Stack>
    )
  }

  const p = persona.data
  const caducados = vencimientos.data?.filter((v) => v.vigente && v.semaforo === 'rojo') ?? []
  const proximos = vencimientos.data?.filter((v) => v.vigente && v.semaforo === 'ambar') ?? []

  return (
    <Stack>
      <VolverAlListado />
      <Group gap="sm" align="center">
        <Title order={2}>{p.nombre}</Title>
        <Badge variant="light">{nombresPuesto[p.puesto]}</Badge>
        {!p.activo && (
          <Badge color="gray" variant="light">
            De baja desde el {formatoFecha(p.fecha_baja!)}
          </Badge>
        )}
      </Group>

      {/* Resumen de la documentación arriba, como la aptitud en la ficha del vehículo. */}
      {caducados.length > 0 && (
        <Alert color="red" icon={<IconCircleX />} title="Documentación caducada">
          {caducados.map((v) => `${v.tipo_nombre}: caducó el ${formatoFecha(v.fecha_caducidad)}`).join(' · ')}
        </Alert>
      )}
      {caducados.length === 0 && proximos.length > 0 && (
        <Alert color="yellow" icon={<IconAlertTriangle />} title="Documentación a punto de caducar">
          {proximos.map((v) => `${v.tipo_nombre}: caduca el ${formatoFecha(v.fecha_caducidad)}`).join(' · ')}
        </Alert>
      )}

      <Tabs defaultValue="datos" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="datos" leftSection={<IconInfoCircle size={16} />}>
            Datos
          </Tabs.Tab>
          <Tabs.Tab value="documentacion" leftSection={<IconFileCertificate size={16} />}>
            Documentación
          </Tabs.Tab>
          <Tabs.Tab value="asignaciones" leftSection={<IconSteeringWheel size={16} />}>
            Vehículos asignados
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="datos" pt="md">
          <PestanaDatos persona={p} />
        </Tabs.Panel>
        <Tabs.Panel value="documentacion" pt="md">
          <Documentacion consulta={vencimientos} />
        </Tabs.Panel>
        <Tabs.Panel value="asignaciones" pt="md">
          {asignaciones.isPending && <Cargando />}
          {asignaciones.error && <ErrorCarga error={asignaciones.error} />}
          {asignaciones.data && (
            <HistorialAsignaciones
              asignaciones={asignaciones.data}
              mostrar="vehiculo"
              puedeFinalizar={puedeGestionarFlota(usuario)}
            />
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

function VolverAlListado() {
  return (
    <Anchor component={Link} to="/personal" size="sm">
      <Group gap={4}>
        <IconArrowLeft size={16} /> Personal
      </Group>
    </Anchor>
  )
}

function PestanaDatos({ persona: p }: { persona: Persona }) {
  const centros = useCentros()
  const centro = centros.data?.find((c) => c.id === p.centro_id)
  return (
    // Solo datos mínimos (RGPD): no hay DNI, teléfono ni datos bancarios que mostrar.
    <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="lg">
      <Dato etiqueta="Nombre" valor={p.nombre} />
      <Dato etiqueta="Puesto" valor={nombresPuesto[p.puesto]} />
      <Dato etiqueta="Centro" valor={centro?.nombre ?? '—'} />
      <Dato etiqueta="Fecha de alta" valor={formatoFecha(p.fecha_alta)} />
      <Dato etiqueta="Estado" valor={p.activo ? 'Activo/a' : `De baja (${formatoFecha(p.fecha_baja!)})`} />
      <Dato etiqueta="Usuario de la aplicación" valor={p.usuario_id ? 'Sí' : 'No'} />
    </SimpleGrid>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {etiqueta}
      </Text>
      <Text>{valor}</Text>
    </div>
  )
}
