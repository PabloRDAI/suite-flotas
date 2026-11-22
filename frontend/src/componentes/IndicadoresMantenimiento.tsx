// Indicadores de mantenimiento (MAN-08) en el panel: últimos 6 meses.
//
// Tres piezas:
//  1. Fila de cifras clave (coste, €/km, averías, días parado, % preventivo).
//  2. Barra segmentada: qué parte del coste fue preventivo y qué parte correctivo.
//  3. Tabla por vehículo, de mayor a menor coste (sirve también de "vista en tabla").
//
// Colores de la barra: azul/naranja validados (contraste, daltonismo) para fondo claro
// y oscuro; el texto nunca va en el color de la serie, salvo el porcentaje DENTRO del
// bloque, que va en blanco.

import { Anchor, Box, Button, Card, Group, SimpleGrid, Stack, Table, Text, Title, Tooltip, useComputedColorScheme } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router'
import { useIndicadores } from '../api/consultas.ts'
import type { Indicadores } from '../api/tipos.ts'
import { formatoEuros, formatoEurosKm, formatoFecha, formatoKm, formatoNumero, formatoPorcentaje } from '../util/formato.ts'
import { BotonExportar } from './BotonExportar.tsx'
import { Cargando, ErrorCarga } from './Carga.tsx'

const COLORES = {
  light: { preventivo: '#2a78d6', correctivo: '#eb6834' },
  dark: { preventivo: '#3987e5', correctivo: '#d95926' },
} as const

// Por debajo de este porcentaje el bloque es demasiado estrecho para escribir dentro.
const MINIMO_PARA_ETIQUETA = 12

// Filas visibles de la tabla antes de pulsar "Ver todos".
const FILAS_INICIALES = 10

export function IndicadoresMantenimiento({ centroId, tipoId }: { centroId: string | null; tipoId: string | null }) {
  const indicadores = useIndicadores(centroId, tipoId)

  return (
    <Card withBorder>
      <Stack>
        <div>
          <Title order={3} size="h4">
            Mantenimiento
          </Title>
          {indicadores.data && (
            <Text c="dimmed" size="sm">
              Últimos 6 meses: del {formatoFecha(indicadores.data.desde)} al {formatoFecha(indicadores.data.hasta)}
            </Text>
          )}
        </div>
        {indicadores.isPending && <Cargando />}
        {indicadores.error && <ErrorCarga error={indicadores.error} />}
        {indicadores.data && (
          <>
            <CifrasClave datos={indicadores.data} />
            <RepartoCoste datos={indicadores.data} />
            <TablaCostes datos={indicadores.data} centroId={centroId} tipoId={tipoId} />
          </>
        )}
      </Stack>
    </Card>
  )
}

// --- 1. Cifras clave ---------------------------------------------------------

function CifrasClave({ datos }: { datos: Indicadores }) {
  const f = datos.flota
  const cifras = [
    { texto: 'Coste de mantenimiento', valor: formatoEuros(f.coste), detalle: `${f.ot_cerradas} OT cerradas` },
    { texto: 'Coste por km', valor: f.coste_por_km === null ? '—' : formatoEurosKm(f.coste_por_km), detalle: `${formatoKm(f.km_recorridos)} recorridos` },
    { texto: 'Averías comunicadas', valor: formatoNumero(f.averias), detalle: 'en el periodo' },
    { texto: 'Días de inmovilización', valor: formatoNumero(f.dias_inmovilizado), detalle: 'sumando todos los vehículos' },
    {
      texto: 'Mantenimiento preventivo',
      valor: f.pct_preventivo_ot === null ? '—' : formatoPorcentaje(f.pct_preventivo_ot),
      detalle: `${f.ot_preventivas} de ${f.ot_cerradas} OT cerradas`,
    },
  ]
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 3, lg: 5 }}>
      {cifras.map((c) => (
        <Card key={c.texto} withBorder padding="sm" bg="var(--mantine-color-default-hover)">
          <Text size="sm" c="dimmed">
            {c.texto}
          </Text>
          <Text fz={26} fw={600} lh={1.3}>
            {c.valor}
          </Text>
          <Text size="xs" c="dimmed">
            {c.detalle}
          </Text>
        </Card>
      ))}
    </SimpleGrid>
  )
}

// --- 2. Reparto del coste: preventivo frente a correctivo -------------------

function RepartoCoste({ datos }: { datos: Indicadores }) {
  const esquema = useComputedColorScheme('light')
  const colores = COLORES[esquema]
  const f = datos.flota

  if (f.coste === 0 || f.pct_preventivo_coste === null) {
    return (
      <Text size="sm" c="dimmed">
        Sin OT cerradas con coste en el periodo.
      </Text>
    )
  }
  const pctPrev = f.pct_preventivo_coste
  // El correctivo es el resto (así los dos suman 100 % aunque cada uno esté redondeado).
  const partes = [
    { nombre: 'Preventivo', importe: f.coste_preventivo, pct: pctPrev, color: colores.preventivo },
    { nombre: 'Correctivo', importe: f.coste_correctivo, pct: Math.round((100 - pctPrev) * 10) / 10, color: colores.correctivo },
  ].filter((p) => p.importe > 0) // una parte a cero no se dibuja
  const descripcion = partes.map((p) => `${p.nombre}: ${formatoEuros(p.importe)} (${formatoPorcentaje(p.pct)})`).join('; ')

  return (
    <div>
      <Text size="sm" fw={500} mb={6}>
        Reparto del coste
      </Text>
      {/* La separación de 2 px entre bloques deja ver el fondo: separa sin bordes. */}
      <Group gap={2} wrap="nowrap" h={28} role="img" aria-label={`Reparto del coste. ${descripcion}`}>
        {partes.map((p) => (
          <Tooltip key={p.nombre} label={`${p.nombre}: ${formatoEuros(p.importe)} · ${formatoPorcentaje(p.pct)}`} withArrow>
            <Box
              tabIndex={0}
              aria-label={`${p.nombre}: ${formatoEuros(p.importe)}, ${formatoPorcentaje(p.pct)}`}
              h="100%"
              style={{
                flex: `${p.importe} 1 0`,
                minWidth: 4,
                background: p.color,
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                paddingInline: 8,
              }}
            >
              {p.pct >= MINIMO_PARA_ETIQUETA && (
                <Text size="sm" fw={600} c="#ffffff" style={{ whiteSpace: 'nowrap' }}>
                  {formatoPorcentaje(p.pct)}
                </Text>
              )}
            </Box>
          </Tooltip>
        ))}
      </Group>
      {/* Leyenda: muestra + nombre + importe (el % ya va dentro del bloque). */}
      <Group gap="lg" mt={8}>
        {partes.map((p) => (
          <Group key={p.nombre} gap={6} wrap="nowrap">
            <Box w={10} h={10} style={{ background: p.color, borderRadius: 2 }} aria-hidden />
            <Text size="sm">{p.nombre}</Text>
            <Text size="sm" c="dimmed">
              {formatoEuros(p.importe)}
            </Text>
          </Group>
        ))}
      </Group>
    </div>
  )
}

// --- 3. Tabla por vehículo ---------------------------------------------------

function TablaCostes({ datos, centroId, tipoId }: { datos: Indicadores; centroId: string | null; tipoId: string | null }) {
  const [todos, setTodos] = useState(false)
  const filas = todos ? datos.vehiculos : datos.vehiculos.slice(0, FILAS_INICIALES)
  const cifra = { fontVariantNumeric: 'tabular-nums' } as const // columnas de números alineadas

  return (
    <div>
      <Group justify="space-between" mb={6}>
        <Text size="sm" fw={500}>
          Por vehículo (de mayor a menor coste)
        </Text>
        <BotonExportar
          ruta="/panel/indicadores/exportar"
          nombre="costes-por-vehiculo"
          filtros={{ desde: datos.desde, hasta: datos.hasta, centro_id: centroId, tipo_id: tipoId }}
        />
      </Group>
      <Table.ScrollContainer minWidth={700}>
        <Table striped highlightOnHover verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Matrícula</Table.Th>
              <Table.Th ta="right">Coste</Table.Th>
              <Table.Th ta="right">Km recorridos</Table.Th>
              <Table.Th ta="right">Coste por km</Table.Th>
              <Table.Th ta="right">Averías</Table.Th>
              <Table.Th ta="right">Días parado</Table.Th>
              <Table.Th ta="right">OT preventivas / correctivas</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filas.map((v) => (
              <Table.Tr key={v.vehiculo_id}>
                <Table.Td>
                  <Anchor component={Link} to={`/vehiculos/${v.vehiculo_id}`} ff="monospace" fw={600}>
                    {v.matricula}
                  </Anchor>
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {formatoEuros(v.coste)}
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {formatoKm(v.km_recorridos)}
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {v.coste_por_km === null ? '—' : formatoEurosKm(v.coste_por_km)}
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {v.averias}
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {v.dias_inmovilizado}
                </Table.Td>
                <Table.Td ta="right" style={cifra}>
                  {v.ot_preventivas} / {v.ot_correctivas}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {datos.vehiculos.length > FILAS_INICIALES && (
        <Button variant="subtle" size="xs" mt={4} onClick={() => setTodos(!todos)}>
          {todos ? 'Ver menos' : `Ver los ${datos.vehiculos.length} vehículos`}
        </Button>
      )}
    </div>
  )
}
