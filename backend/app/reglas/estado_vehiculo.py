"""Motor de estado del vehículo (regla 1 de la spec, FLO-03).

    Estado = de baja       si el vehículo está inactivo;
             en taller     si tiene una OT abierta que inmoviliza;
             inmovilizado  si tiene una avería "inmoviliza" sin OT abierta;
             operativo     en otro caso.

Las condiciones se comprueban en ese orden: la primera que se cumple decide.

Esta regla no sabe nada de la base de datos: recibe resúmenes de las órdenes de
trabajo y averías del vehículo. El servicio app/servicios/estado_vehiculo.py es
quien los reúne de la BD y guarda el resultado.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class EstadoVehiculo(StrEnum):
    OPERATIVO = "operativo"
    EN_TALLER = "en_taller"
    INMOVILIZADO = "inmovilizado"
    BAJA = "baja"


class EstadoOT(StrEnum):
    """Flujo de una orden de trabajo (MAN-05): abierta → en curso → cerrada (o cancelada)."""

    ABIERTA = "abierta"
    EN_CURSO = "en_curso"
    CERRADA = "cerrada"
    CANCELADA = "cancelada"


class GravedadAveria(StrEnum):
    """MAN-03: leve, grave o inmoviliza."""

    LEVE = "leve"
    GRAVE = "grave"
    INMOVILIZA = "inmoviliza"


class EstadoAveria(StrEnum):
    COMUNICADA = "comunicada"  # recién comunicada, sin OT
    EN_REPARACION = "en_reparacion"  # tiene una OT (MAN-04)
    RESUELTA = "resuelta"


# Una OT "abierta" a efectos de la regla es la que aún no ha terminado.
ESTADOS_OT_ABIERTA = frozenset({EstadoOT.ABIERTA, EstadoOT.EN_CURSO})


@dataclass(frozen=True)
class ResumenOT:
    estado: EstadoOT
    inmoviliza: bool

    @property
    def abierta(self) -> bool:
        return self.estado in ESTADOS_OT_ABIERTA


@dataclass(frozen=True)
class ResumenAveria:
    gravedad: GravedadAveria
    estado: EstadoAveria
    # ¿Está enlazada a una OT que sigue abierta? Si la OT se cancela, vuelve a ser "sin OT".
    con_ot_abierta: bool


def calcular_estado(activo: bool, ordenes: Iterable[ResumenOT], averias: Iterable[ResumenAveria]) -> EstadoVehiculo:
    """Aplica la regla 1 y devuelve el estado que corresponde al vehículo."""
    if not activo:
        return EstadoVehiculo.BAJA

    if any(ot.abierta and ot.inmoviliza for ot in ordenes):
        return EstadoVehiculo.EN_TALLER

    if any(
        a.gravedad == GravedadAveria.INMOVILIZA and a.estado != EstadoAveria.RESUELTA and not a.con_ot_abierta
        for a in averias
    ):
        return EstadoVehiculo.INMOVILIZADO

    return EstadoVehiculo.OPERATIVO
