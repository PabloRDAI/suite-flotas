"""Mantiene Vehiculo.estado al día aplicando la regla 1 (FLO-03).

    actualizar_estado(db, vehiculo)

Debe llamarse después de cualquier cambio que pueda alterar el estado:
- dar de baja un vehículo (ya conectado);
- abrir, cerrar o cancelar una orden de trabajo (MAN-04, MAN-05);
- comunicar o resolver una avería (MAN-03).

Se diseñó con _ordenes() y _averias() vacías, antes de que existieran las averías y las
OT; desde MAN-03 y MAN-04 leen las reales. La regla y sus tests no han cambiado.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Averia, OrdenTrabajo, Vehiculo
from app.reglas.estado_vehiculo import (
    ESTADOS_OT_ABIERTA,
    EstadoAveria,
    EstadoVehiculo,
    ResumenAveria,
    ResumenOT,
    calcular_estado,
)


def _ordenes(db: Session, vehiculo: Vehiculo) -> list[ResumenOT]:
    """Órdenes de trabajo abiertas o en curso del vehículo (las cerradas o canceladas no influyen)."""
    ordenes = db.scalars(
        select(OrdenTrabajo).where(OrdenTrabajo.vehiculo_id == vehiculo.id, OrdenTrabajo.estado.in_(ESTADOS_OT_ABIERTA))
    )
    return [ResumenOT(ot.estado, ot.inmoviliza) for ot in ordenes]


def _averias(db: Session, vehiculo: Vehiculo) -> list[ResumenAveria]:
    """Averías no resueltas del vehículo, indicando si tienen una OT abierta (MAN-04)."""
    averias = list(
        db.scalars(select(Averia).where(Averia.vehiculo_id == vehiculo.id, Averia.estado != EstadoAveria.RESUELTA))
    )
    con_ot = set(
        db.scalars(
            select(OrdenTrabajo.averia_id).where(
                OrdenTrabajo.averia_id.in_([a.id for a in averias]), OrdenTrabajo.estado.in_(ESTADOS_OT_ABIERTA)
            )
        )
    )
    return [ResumenAveria(a.gravedad, a.estado, con_ot_abierta=a.id in con_ot) for a in averias]


def actualizar_estado(db: Session, vehiculo: Vehiculo) -> EstadoVehiculo:
    """Recalcula el estado del vehículo, lo asigna y lo devuelve (no hace commit).

    El commit lo hace quien llama, junto con el resto de cambios de la operación:
    así, si algo falla, no queda el estado cambiado a medias.
    """
    nuevo = calcular_estado(vehiculo.activo, _ordenes(db, vehiculo), _averias(db, vehiculo))
    vehiculo.estado = nuevo
    return nuevo
