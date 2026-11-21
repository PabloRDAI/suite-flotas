"""Mantiene Vehiculo.estado al día aplicando la regla 1 (FLO-03).

    actualizar_estado(db, vehiculo)

Debe llamarse después de cualquier cambio que pueda alterar el estado:
- dar de baja un vehículo (ya conectado);
- abrir, cerrar o cancelar una orden de trabajo (MAN-04, MAN-05);
- comunicar o resolver una avería (MAN-03).

Hoy todavía no existen las tablas de averías ni de órdenes de trabajo, así que
_ordenes() y _averias() devuelven listas vacías. Cuando existan, SOLO habrá que
rellenar esas dos funciones: la regla y sus tests no cambian.
"""

from sqlalchemy.orm import Session

from app.models import Vehiculo
from app.reglas.estado_vehiculo import EstadoVehiculo, ResumenAveria, ResumenOT, calcular_estado


def _ordenes(db: Session, vehiculo: Vehiculo) -> list[ResumenOT]:
    """Resumen de las órdenes de trabajo del vehículo (pendiente: fase de mantenimiento)."""
    return []


def _averias(db: Session, vehiculo: Vehiculo) -> list[ResumenAveria]:
    """Resumen de las averías del vehículo (pendiente: fase de mantenimiento)."""
    return []


def actualizar_estado(db: Session, vehiculo: Vehiculo) -> EstadoVehiculo:
    """Recalcula el estado del vehículo, lo asigna y lo devuelve (no hace commit).

    El commit lo hace quien llama, junto con el resto de cambios de la operación:
    así, si algo falla, no queda el estado cambiado a medias.
    """
    nuevo = calcular_estado(vehiculo.activo, _ordenes(db, vehiculo), _averias(db, vehiculo))
    vehiculo.estado = nuevo
    return nuevo
