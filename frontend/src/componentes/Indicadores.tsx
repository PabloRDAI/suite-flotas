// Indicadores de estado con color + icono + texto (requisito de usabilidad de la spec:
// "colores de alerta coherentes, siempre con texto o icono, no solo color").

import { Badge } from '@mantine/core'
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleX,
  IconHandStop,
  IconTool,
  IconArchive,
  IconClockHour4,
} from '@tabler/icons-react'
import type { EstadoVehiculo as Estado, Semaforo, SituacionPreventivo } from '../api/tipos.ts'

const SEMAFORO = {
  verde: { color: 'green', texto: 'En regla', Icono: IconCircleCheck },
  ambar: { color: 'yellow', texto: 'Caduca pronto', Icono: IconAlertTriangle },
  rojo: { color: 'red', texto: 'Caducado', Icono: IconCircleX },
} as const

/** Semáforo de un vencimiento (FLO-06): verde, ámbar o rojo, siempre con icono y texto. */
export function IndicadorSemaforo({ valor }: { valor: Semaforo }) {
  const { color, texto, Icono } = SEMAFORO[valor]
  return (
    <Badge color={color} variant="light" leftSection={<Icono size={14} aria-hidden />}>
      {texto}
    </Badge>
  )
}

const ESTADO = {
  operativo: { color: 'green', texto: 'Operativo', Icono: IconCircleCheck },
  en_taller: { color: 'orange', texto: 'En taller', Icono: IconTool },
  inmovilizado: { color: 'red', texto: 'Inmovilizado', Icono: IconHandStop },
  baja: { color: 'gray', texto: 'De baja', Icono: IconArchive },
} as const

/** Estado del vehículo (FLO-03), con icono y texto. */
export function EstadoVehiculo({ valor }: { valor: Estado }) {
  const { color, texto, Icono } = ESTADO[valor]
  return (
    <Badge color={color} variant="light" leftSection={<Icono size={14} aria-hidden />}>
      {texto}
    </Badge>
  )
}

const PREVENTIVO = {
  al_dia: { color: 'green', texto: 'Al día', Icono: IconCircleCheck },
  proximo: { color: 'yellow', texto: 'Próximo', Icono: IconClockHour4 },
  vencido: { color: 'red', texto: 'Vencido', Icono: IconCircleX },
} as const

/** Situación de un preventivo (MAN-01, MAN-02), con icono y texto. */
export function IndicadorPreventivo({ valor }: { valor: SituacionPreventivo }) {
  const { color, texto, Icono } = PREVENTIVO[valor]
  return (
    <Badge color={color} variant="light" leftSection={<Icono size={14} aria-hidden />}>
      {texto}
    </Badge>
  )
}
