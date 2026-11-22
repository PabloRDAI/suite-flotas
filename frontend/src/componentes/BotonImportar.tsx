// Botón "Importar" de Vehículos y Personal (GEN-05): plantilla, subida y resultado.
//
// La importación es "todo o nada": si alguna fila tiene errores, no se crea nada y aquí se
// listan todas las filas con su motivo, para corregirlas en el Excel y volver a subirlo.

import { Alert, Anchor, Button, FileInput, Group, Modal, ScrollArea, Stack, Table, Text } from '@mantine/core'
import { IconCircleCheck, IconDownload, IconFileUpload, IconUpload } from '@tabler/icons-react'
import { type FormEvent, useState } from 'react'
import { ErrorApi, guardarArchivo } from '../api/cliente.ts'
import { type QueImportar, useImportar } from '../api/consultas.ts'

type ErrorFila = { fila: number | null; columna: string | null; motivo: string }

const TEXTOS: Record<QueImportar, { titulo: string; plural: string; plantilla: string }> = {
  vehiculos: { titulo: 'Importar vehículos', plural: 'vehículos', plantilla: 'plantilla-vehiculos.xlsx' },
  personas: { titulo: 'Importar personal', plural: 'personas', plantilla: 'plantilla-personal.xlsx' },
}

export function BotonImportar({ que }: { que: QueImportar }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <>
      <Button variant="default" leftSection={<IconFileUpload size={16} />} onClick={() => setAbierto(true)}>
        Importar
      </Button>
      <Modal opened={abierto} onClose={() => setAbierto(false)} title={TEXTOS[que].titulo} size="lg">
        {abierto && <Importar que={que} alCerrar={() => setAbierto(false)} />}
      </Modal>
    </>
  )
}

function Importar({ que, alCerrar }: { que: QueImportar; alCerrar: () => void }) {
  const textos = TEXTOS[que]
  const importar = useImportar(que)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [errorPlantilla, setErrorPlantilla] = useState<string | null>(null)

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    if (archivo) importar.mutate(archivo)
  }
  const descargarPlantilla = () => {
    setErrorPlantilla(null)
    guardarArchivo(`/importar/${que}/plantilla`, textos.plantilla).catch((e: Error) => setErrorPlantilla(e.message))
  }

  if (importar.data) {
    return (
      <Stack>
        <Group gap="xs" c="green">
          <IconCircleCheck size={20} aria-hidden />
          <Text fw={500}>
            Se han importado {importar.data.importados} {textos.plural}.
          </Text>
        </Group>
        <Group justify="end">
          <Button onClick={alCerrar}>Cerrar</Button>
        </Group>
      </Stack>
    )
  }

  // Si la API devolvió la lista de filas con errores, se muestra en una tabla.
  const detalle = importar.error instanceof ErrorApi ? (importar.error.detalle as { errores?: ErrorFila[] } | undefined) : undefined
  const errores = detalle?.errores?.filter((e) => e.fila !== null) ?? []

  return (
    <form onSubmit={enviar}>
      <Stack>
        <Text size="sm">
          1.{' '}
          <Anchor component="button" type="button" onClick={descargarPlantilla} inline>
            <IconDownload size={14} style={{ verticalAlign: 'middle' }} /> Descarga la plantilla
          </Anchor>{' '}
          (trae dos filas de ejemplo y una hoja con los valores admitidos) y rellénala en Excel.
        </Text>
        {errorPlantilla && <Alert color="red">{errorPlantilla}</Alert>}
        <FileInput
          label="2. Sube el archivo"
          description="Excel (.xlsx) o CSV, de hasta 2 MB y 1.000 filas"
          placeholder="Elegir archivo…"
          accept=".xlsx,.csv"
          leftSection={<IconUpload size={16} />}
          value={archivo}
          onChange={(f) => {
            setArchivo(f)
            importar.reset() // al cambiar de archivo, se borra el resultado anterior
          }}
          clearable
          required
        />
        <Text size="xs" c="dimmed">
          Se importa todo o nada: si alguna fila tiene un error, no se crea ningún registro.
        </Text>

        {importar.error && (
          <Alert color="red" title={importar.error.message}>
            {errores.length > 0 && (
              <ScrollArea.Autosize mah={260} mt="xs">
                <Table verticalSpacing={4} fz="sm" withRowBorders={false}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th w={50}>Fila</Table.Th>
                      <Table.Th w={120}>Columna</Table.Th>
                      <Table.Th>Motivo</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {errores.map((e) => (
                      <Table.Tr key={`${e.fila}-${e.columna}-${e.motivo}`}>
                        <Table.Td>{e.fila}</Table.Td>
                        <Table.Td>{e.columna ?? '—'}</Table.Td>
                        <Table.Td>{e.motivo}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea.Autosize>
            )}
          </Alert>
        )}

        <Group justify="end">
          <Button variant="default" onClick={alCerrar}>
            Cancelar
          </Button>
          <Button type="submit" loading={importar.isPending} disabled={!archivo}>
            Importar
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
