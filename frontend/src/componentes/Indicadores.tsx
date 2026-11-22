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
  IconPlayerPlay,
  IconCalendarRepeat,
  IconBan,
  IconInbox,
} from '@tabler/icons-react'
import type { EstadoOT as EstadoOrden, EstadoVehiculo as Estado, Semaforo, SituacionPreventivo, TipoOT } from '../api/tipos.ts'

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

const ESTADO_OT = {
  abierta: { color: 'yellow', texto: 'Abierta', Icono: IconInbox },
  en_curso: { color: 'blue', texto: 'En curso', Icono: IconPlayerPlay },
  cerrada: { color: 'green', texto: 'Cerrada', Icono: IconCircleCheck },
  cancelada: { color: 'gray', texto: 'Cancelada', Icono: IconBan },
} as const

/** Estado de una orden de trabajo (MAN-05), con icono y texto. */
export function EstadoOT({ valor }: { valor: EstadoOrden }) {
  const { color, texto, Icono } = ESTADO_OT[valor]
  return (
    <Badge color={color} variant="light" leftSection={<Icono size={14} aria-hidden />}>
      {texto}
    </Badge>
  )
}

/** Preventiva (programada) o correctiva (reparación). */
export function TipoOrden({ valor }: { valor: TipoOT }) {
  return valor === 'preventiva' ? (
    <Badge color="teal" variant="outline" leftSection={<IconCalendarRepeat size={14} aria-hidden />}>
      Preventiva
    </Badge>
  ) : (
    <Badge color="orange" variant="outline" leftSection={<IconTool size={14} aria-hidden />}>
      Correctiva
    </Badge>
  )
}
