"""Mantiene Vehiculo.estado al día aplicando la regla 1 (FLO-03).

    actualizar_estado(db, vehiculo)

Debe llamarse después de cualquier cambio que pueda alterar el estado:
- dar de baja un vehículo (ya conectado);
- abrir, cerrar o cancelar una orden de trabajo (MAN-04, MAN-05);
- comunicar o resolver una avería (MAN-03).

Las averías ya existen (MAN-03). Las órdenes de trabajo todavía no, así que
_ordenes() devuelve una lista vacía: cuando existan, SOLO habrá que rellenarla
(y con_ot_abierta de las averías). La regla y sus tests no cambian.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Averia, Vehiculo
from app.reglas.estado_vehiculo import EstadoAveria, EstadoVehiculo, ResumenAveria, ResumenOT, calcular_estado


def _ordenes(db: Session, vehiculo: Vehiculo) -> list[ResumenOT]:
    """Resumen de las órdenes de trabajo del vehículo (pendiente: MAN-04)."""
    return []


def _averias(db: Session, vehiculo: Vehiculo) -> list[ResumenAveria]:
    """Averías no resueltas del vehículo (las resueltas no influyen en su estado)."""
    averias = db.scalars(
        select(Averia).where(Averia.vehiculo_id == vehiculo.id, Averia.estado != EstadoAveria.RESUELTA)
    )
    # con_ot_abierta=False hasta que existan las órdenes de trabajo (MAN-04).
    return [ResumenAveria(a.gravedad, a.estado, con_ot_abierta=False) for a in averias]


def actualizar_estado(db: Session, vehiculo: Vehiculo) -> EstadoVehiculo:
    """Recalcula el estado del vehículo, lo asigna y lo devuelve (no hace commit).

    El commit lo hace quien llama, junto con el resto de cambios de la operación:
    así, si algo falla, no queda el estado cambiado a medias.
    """
    nuevo = calcular_estado(vehiculo.activo, _ordenes(db, vehiculo), _averias(db, vehiculo))
    vehiculo.estado = nuevo
    return nuevo
