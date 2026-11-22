// Catálogo de recambios (MAN-09): referencia, nombre y precio por defecto. Sin stock.
//
// Lo consulta cualquiera; lo gestionan el gerente y el jefe de taller. El precio del
// catálogo se copia a la OT al añadir el recambio: cambiarlo aquí no altera las OT ya hechas.

import { Alert, Button, Group, Modal, NumberInput, Stack, Switch, Table, Text, TextInput, Title } from '@mantine/core'
import { IconPencil, IconPlus, IconSearch, IconTrash } from '@tabler/icons-react'
import { type FormEvent, useMemo, useState } from 'react'
import { useBajaRecambio, useGuardarRecambio, useRecambios } from '../api/consultas.ts'
import type { Recambio } from '../api/tipos.ts'
import { useSesion } from '../auth/contexto.ts'
import { puedeGestionarTaller } from '../auth/permisos.ts'
import { BotonExportar } from '../componentes/BotonExportar.tsx'
import { Cargando, ErrorCarga } from '../componentes/Carga.tsx'
import { formatoEuros } from '../util/formato.ts'

export default function Recambios() {
  const { usuario } = useSesion()
  const gestiona = puedeGestionarTaller(usuario)
  const [incluirBajas, setIncluirBajas] = useState(false)
  const [texto, setTexto] = useState('')
  // undefined: modal cerrado · null: alta · Recambio: edición
  const [editando, setEditando] = useState<Recambio | null | undefined>(undefined)
  const [quitando, setQuitando] = useState<Recambio | null>(null) // pendiente de confirmar la baja
  const recambios = useRecambios(incluirBajas)
  const baja = useBajaRecambio()

  const filtrados = useMemo(() => {
    const busqueda = texto.trim().toLowerCase()
    return (recambios.data ?? []).filter(
      (r) => !busqueda || r.referencia.toLowerCase().includes(busqueda) || r.nombre.toLowerCase().includes(busqueda),
    )
  }, [recambios.data, texto])

  return (
    <Stack>
      <Group justify="space-between" align="baseline">
        <Title order={2}>Recambios</Title>
        {recambios.data && (
          <Text c="dimmed" size="sm" aria-live="polite">
            {filtrados.length} de {recambios.data.length}
          </Text>
        )}
      </Group>
      <Text size="sm" c="dimmed">
        El precio es el precio por defecto: se copia a la orden de trabajo al añadir el recambio, y ahí se puede ajustar.
      </Text>

      <Group align="end" gap="sm">
        <TextInput
          label="Buscar"
          placeholder="Referencia o nombre"
          leftSection={<IconSearch size={16} />}
          value={texto}
          onChange={(e) => setTexto(e.currentTarget.value)}
          w={{ base: '100%', sm: 240 }}
        />
        <Switch label="Incluir los dados de baja" checked={incluirBajas} onChange={(e) => setIncluirBajas(e.currentTarget.checked)} mb={8} />
        <Group ml="auto">
          <BotonExportar ruta="/recambios/exportar" nombre="recambios" filtros={{ buscar: texto.trim(), incluir_bajas: incluirBajas }} />
          {gestiona && (
            <Button leftSection={<IconPlus size={16} />} onClick={() => setEditando(null)}>
              Nuevo recambio
            </Button>
          )}
        </Group>
      </Group>

      {recambios.isPending && <Cargando />}
      {recambios.error && <ErrorCarga error={recambios.error} />}
      {recambios.data && (
        <Table.ScrollContainer minWidth={560}>
          <Table striped highlightOnHover verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Referencia</Table.Th>
                <Table.Th>Nombre</Table.Th>
                <Table.Th ta="right">Precio</Table.Th>
                {gestiona && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtrados.map((r) => (
                <Table.Tr key={r.id} c={r.activo ? undefined : 'dimmed'}>
                  <Table.Td ff="monospace">{r.referencia}</Table.Td>
                  <Table.Td>
                    {r.nombre}
                    {!r.activo && ' (de baja)'}
                  </Table.Td>
                  <Table.Td ta="right" style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {formatoEuros(r.precio)}
                  </Table.Td>
                  {gestiona && (
                    <Table.Td ta="right">
                      {r.activo && (
                        <Group gap={4} justify="end" wrap="nowrap">
                          <Button variant="subtle" size="compact-sm" leftSection={<IconPencil size={14} />} onClick={() => setEditando(r)}>
                            Editar
                          </Button>
                          <Button
                            variant="subtle"
                            color="red"
                            size="compact-sm"
                            leftSection={<IconTrash size={14} />}
                            onClick={() => setQuitando(r)}
                          >
                            Dar de baja
                          </Button>
                        </Group>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
              {filtrados.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={4}>
                    <Text c="dimmed" ta="center" py="md">
                      {recambios.data.length === 0 ? 'El catálogo está vacío.' : 'Ningún recambio coincide con la búsqueda.'}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal opened={editando !== undefined} onClose={() => setEditando(undefined)} title={editando ? 'Editar recambio' : 'Nuevo recambio'}>
        {editando !== undefined && <FormularioRecambio recambio={editando} alTerminar={() => setEditando(undefined)} />}
      </Modal>

      <Modal opened={quitando !== null} onClose={() => setQuitando(null)} title="Dar de baja el recambio">
        <Stack>
          <Text>
            «{quitando?.nombre}» dejará de ofrecerse al añadir recambios. Las órdenes de trabajo que ya lo usan no cambian.
          </Text>
          {baja.error && <Alert color="red">{baja.error.message}</Alert>}
          <Group justify="end">
            <Button variant="default" onClick={() => setQuitando(null)}>
              Cancelar
            </Button>
            <Button color="red" loading={baja.isPending} onClick={() => quitando && baja.mutate(quitando.id, { onSuccess: () => setQuitando(null) })}>
              Dar de baja
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

function FormularioRecambio({ recambio, alTerminar }: { recambio: Recambio | null; alTerminar: () => void }) {
  const guardar = useGuardarRecambio()
  const [referencia, setReferencia] = useState(recambio?.referencia ?? '')
  const [nombre, setNombre] = useState(recambio?.nombre ?? '')
  const [precio, setPrecio] = useState<number | string>(recambio?.precio ?? '')

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    guardar.mutate({ id: recambio?.id, referencia, nombre, precio: Number(precio) }, { onSuccess: alTerminar })
  }

  return (
    <form onSubmit={enviar}>
      <Stack>
        <TextInput label="Referencia" required maxLength={40} value={referencia} onChange={(e) => setReferencia(e.currentTarget.value)} data-autofocus />
        <TextInput label="Nombre" required maxLength={150} value={nombre} onChange={(e) => setNombre(e.currentTarget.value)} />
        <NumberInput label="Precio por defecto (€)" required min={0} decimalScale={2} decimalSeparator="," value={precio} onChange={setPrecio} />
        {recambio && <Text size="xs" c="dimmed">Cambiar el precio no altera las órdenes de trabajo ya registradas.</Text>}
        {guardar.error && <Alert color="red">{guardar.error.message}</Alert>}
        <Group justify="end">
          <Button variant="default" onClick={alTerminar}>
            Cancelar
          </Button>
          <Button type="submit" loading={guardar.isPending}>
            Guardar
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
