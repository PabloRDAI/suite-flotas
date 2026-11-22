// Listado del personal con el semáforo de su documentación (PER-01, PER-02).

import { Anchor, Badge, Group, Select, Stack, Switch, Table, Text, TextInput, Title } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useCentros, usePersonas } from '../api/consultas.ts'
import type { Semaforo } from '../api/tipos.ts'
import { BotonExportar } from '../componentes/BotonExportar.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { IndicadorSemaforo } from '../componentes/Indicadores.tsx'
import { formatoFecha, nombresPuesto } from '../util/formato.ts'

const ORDEN: Record<Semaforo, number> = { rojo: 0, ambar: 1, verde: 2 }

export default function Personal() {
  const [incluirBajas, setIncluirBajas] = useState(false)
  const [texto, setTexto] = useState('')
  const [puesto, setPuesto] = useState<string | null>(null)
  const [centroId, setCentroId] = useState<string | null>(null)
  const [documentacion, setDocumentacion] = useState<string | null>(null)

  const personas = usePersonas(incluirBajas)
  const centros = useCentros()
  const nombreCentro = useMemo(() => new Map(centros.data?.map((c) => [c.id, c.nombre])), [centros.data])

  const filtradas = useMemo(() => {
    const busqueda = texto.trim().toLowerCase()
    return (personas.data ?? [])
      .filter(
        (p) =>
          (!busqueda || p.nombre.toLowerCase().includes(busqueda)) &&
          (!puesto || p.puesto === puesto) &&
          (!centroId || p.centro_id === Number(centroId)) &&
          (!documentacion || p.semaforo === documentacion),
      )
      // Primero quien necesita atención (documentación en rojo, luego ámbar); después, por nombre.
      .sort((a, b) => ORDEN[a.semaforo] - ORDEN[b.semaforo] || a.nombre.localeCompare(b.nombre, 'es'))
  }, [personas.data, texto, puesto, centroId, documentacion])

  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Personal</Title>
        {personas.data && (
          <Text c="dimmed" size="sm" aria-live="polite">
            {filtradas.length} de {personas.data.length}
          </Text>
        )}
      </Group>

      <Group align="end" gap="sm">
        <TextInput
          label="Buscar"
          placeholder="Nombre"
          leftSection={<IconSearch size={16} />}
          value={texto}
          onChange={(e) => setTexto(e.currentTarget.value)}
          w={{ base: '100%', sm: 220 }}
        />
        <Select
          label="Puesto"
          placeholder="Todos"
          clearable
          data={Object.entries(nombresPuesto).map(([value, label]) => ({ value, label }))}
          value={puesto}
          onChange={setPuesto}
          w={{ base: '100%', sm: 150 }}
        />
        <Select
          label="Centro"
          placeholder="Todos"
          clearable
          data={centros.data?.map((c) => ({ value: String(c.id), label: c.nombre })) ?? []}
          value={centroId}
          onChange={setCentroId}
          w={{ base: '100%', sm: 180 }}
        />
        <Select
          label="Documentación"
          placeholder="Toda"
          clearable
          data={[
            { value: 'rojo', label: 'Caducada' },
            { value: 'ambar', label: 'Caduca pronto' },
            { value: 'verde', label: 'En regla' },
          ]}
          value={documentacion}
          onChange={setDocumentacion}
          w={{ base: '100%', sm: 160 }}
        />
        <Switch label="Incluir bajas" checked={incluirBajas} onChange={(e) => setIncluirBajas(e.currentTarget.checked)} mb={8} />
        <Group ml="auto">
          <BotonExportar
            ruta="/personas/exportar"
            nombre="personal"
            filtros={{ buscar: texto.trim(), puesto, centro_id: centroId, semaforo: documentacion, incluir_bajas: incluirBajas }}
          />
        </Group>
      </Group>

      {personas.isPending && <Cargando />}
      {personas.error && <ErrorCarga error={personas.error} />}
      {personas.data && (
        <Table.ScrollContainer minWidth={640}>
          <Table striped highlightOnHover verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Nombre</Table.Th>
                <Table.Th>Puesto</Table.Th>
                <Table.Th>Centro</Table.Th>
                <Table.Th>Alta</Table.Th>
                <Table.Th>Documentación</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtradas.map((p) => (
                <Table.Tr key={p.id} c={p.activo ? undefined : 'dimmed'}>
                  <Table.Td>
                    <Anchor component={Link} to={`/personal/${p.id}`} fw={600}>
                      {p.nombre}
                    </Anchor>
                    {!p.activo && (
                      <Badge color="gray" variant="light" ml="xs">
                        De baja
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>{nombresPuesto[p.puesto]}</Table.Td>
                  <Table.Td>{nombreCentro.get(p.centro_id) ?? '—'}</Table.Td>
                  <Table.Td>{formatoFecha(p.fecha_alta)}</Table.Td>
                  <Table.Td>
                    <IndicadorSemaforo valor={p.semaforo} />
                  </Table.Td>
                </Table.Tr>
              ))}
              {filtradas.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text c="dimmed" ta="center" py="md">
                      Nadie coincide con los filtros.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
