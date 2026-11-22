// Listado de vehículos con filtros (FLO-01). Al pulsar una fila se abre su ficha.

import { Anchor, Group, Select, Stack, Switch, Table, Text, TextInput, Title } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useCentros, useTiposVehiculo, useVehiculos } from '../api/consultas.ts'
import type { EstadoVehiculo as Estado } from '../api/tipos.ts'
import { BotonExportar } from '../componentes/BotonExportar.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { EstadoVehiculo } from '../componentes/Indicadores.tsx'
import { formatoKm } from '../util/formato.ts'

const OPCIONES_ESTADO: { value: Estado; label: string }[] = [
  { value: 'operativo', label: 'Operativo' },
  { value: 'en_taller', label: 'En taller' },
  { value: 'inmovilizado', label: 'Inmovilizado' },
  { value: 'baja', label: 'De baja' },
]

export default function Vehiculos() {
  const navegar = useNavigate()
  const [incluirBajas, setIncluirBajas] = useState(false)
  const [texto, setTexto] = useState('')
  const [centroId, setCentroId] = useState<string | null>(null)
  const [tipoId, setTipoId] = useState<string | null>(null)
  const [estado, setEstado] = useState<string | null>(null)

  const vehiculos = useVehiculos(incluirBajas)
  const centros = useCentros()
  const tipos = useTiposVehiculo()

  // Diccionarios id -> nombre, para mostrar nombres en lugar de números.
  const nombreCentro = useMemo(() => new Map(centros.data?.map((c) => [c.id, c.nombre])), [centros.data])
  const nombreTipo = useMemo(() => new Map(tipos.data?.map((t) => [t.id, t.nombre])), [tipos.data])

  // Filtrado en el navegador: instantáneo y sin peticiones extra.
  const filtrados = useMemo(() => {
    const busqueda = texto.trim().toLowerCase().replace(/[\s-]/g, '')
    return (vehiculos.data ?? []).filter(
      (v) =>
        (!busqueda || `${v.matricula}${v.marca}${v.modelo}`.toLowerCase().replace(/\s/g, '').includes(busqueda)) &&
        (!centroId || v.centro_id === Number(centroId)) &&
        (!tipoId || v.tipo_id === Number(tipoId)) &&
        (!estado || v.estado === estado),
    )
  }, [vehiculos.data, texto, centroId, tipoId, estado])

  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Vehículos</Title>
        {vehiculos.data && (
          <Text c="dimmed" size="sm" aria-live="polite">
            {filtrados.length} de {vehiculos.data.length}
          </Text>
        )}
      </Group>

      <Group align="end" gap="sm">
        <TextInput
          label="Buscar"
          placeholder="Matrícula, marca o modelo"
          leftSection={<IconSearch size={16} />}
          value={texto}
          onChange={(e) => setTexto(e.currentTarget.value)}
          w={{ base: '100%', sm: 240 }}
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
          label="Tipo"
          placeholder="Todos"
          clearable
          data={tipos.data?.map((t) => ({ value: String(t.id), label: t.nombre })) ?? []}
          value={tipoId}
          onChange={setTipoId}
          w={{ base: '100%', sm: 160 }}
        />
        <Select
          label="Estado"
          placeholder="Todos"
          clearable
          data={OPCIONES_ESTADO}
          value={estado}
          onChange={setEstado}
          w={{ base: '100%', sm: 150 }}
        />
        <Switch
          label="Incluir bajas"
          checked={incluirBajas}
          onChange={(e) => setIncluirBajas(e.currentTarget.checked)}
          mb={8}
        />
        <Group ml="auto">
          <BotonExportar
            ruta="/vehiculos/exportar"
            nombre="vehiculos"
            filtros={{ centro_id: centroId, tipo_id: tipoId, estado, buscar: texto.trim(), incluir_bajas: incluirBajas }}
          />
        </Group>
      </Group>

      {vehiculos.isPending && <Cargando />}
      {vehiculos.error && <ErrorCarga error={vehiculos.error} />}

      {vehiculos.data && (
        // En pantallas estrechas la tabla se desplaza en horizontal en vez de deformarse.
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Matrícula</Table.Th>
                <Table.Th>Tipo</Table.Th>
                <Table.Th>Marca y modelo</Table.Th>
                <Table.Th>Centro</Table.Th>
                <Table.Th ta="right">Km</Table.Th>
                <Table.Th>Estado</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtrados.map((v) => (
                <Table.Tr key={v.id} onClick={() => void navegar(`/vehiculos/${v.id}`)} style={{ cursor: 'pointer' }}>
                  <Table.Td>
                    {/* Enlace real (accesible con teclado y lector de pantalla), además del clic en la fila. */}
                    <Anchor component={Link} to={`/vehiculos/${v.id}`} fw={600} ff="monospace">
                      {v.matricula}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{nombreTipo.get(v.tipo_id) ?? '—'}</Table.Td>
                  <Table.Td>
                    {v.marca} {v.modelo}
                  </Table.Td>
                  <Table.Td>{nombreCentro.get(v.centro_id) ?? '—'}</Table.Td>
                  <Table.Td ta="right">{formatoKm(v.km_actuales)}</Table.Td>
                  <Table.Td>
                    <EstadoVehiculo valor={v.estado} />
                  </Table.Td>
                </Table.Tr>
              ))}
              {filtrados.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={6}>
                    <Text c="dimmed" ta="center" py="md">
                      Ningún vehículo coincide con los filtros.
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
