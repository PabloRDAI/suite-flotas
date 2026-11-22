// Botón "Crear OT" de un preventivo: crea la OT preventiva del plan (MAN-04) y abre su ficha.
// Se usa en la previsión del taller y en la pestaña Mantenimiento de la ficha del vehículo.

import { Button } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router'
import { useCrearOT } from '../api/consultas.ts'
import type { PrevisionItem } from '../api/tipos.ts'

/** Crea la OT preventiva del plan (MAN-04) y abre su ficha. */
export function BotonCrearOTPlan({ p }: { p: Pick<PrevisionItem, 'vehiculo_id' | 'plan_id' | 'plan_nombre' | 'matricula'> }) {
  const crear = useCrearOT()
  const navegar = useNavigate()
  return (
    <Button
      size="xs"
      loading={crear.isPending}
      onClick={() =>
        crear.mutate(
          { vehiculo_id: p.vehiculo_id, plan_id: p.plan_id },
          {
            onSuccess: (ot) => void navegar(`/ordenes-trabajo/${ot.id}`),
            onError: (e) => notifications.show({ color: 'red', message: e.message }),
          },
        )
      }
    >
      Crear OT
    </Button>
  )
}
