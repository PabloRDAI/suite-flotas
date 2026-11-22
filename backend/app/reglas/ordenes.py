"""Reglas de las órdenes de trabajo (MAN-05, MAN-06).

- Flujo (MAN-05): abierta -> en curso -> cerrada, o cancelada desde abierta o en curso.
- Coste (regla 4 de la spec, MAN-06): Σ (cantidad × precio_unitario) de sus líneas.

El dinero se calcula con Decimal, nunca con float: con float, 0.1 + 0.2 da
0.30000000000000004 y los céntimos acaban sin cuadrar.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.reglas.estado_vehiculo import EstadoOT

class TipoOT(StrEnum):
    PREVENTIVA = "preventiva"  # mantenimiento programado (de un plan)
    CORRECTIVA = "correctiva"  # reparar algo que ha fallado


class OrigenOT(StrEnum):
    PLAN = "plan"  # creada desde un plan preventivo
    AVERIA = "averia"  # creada desde una avería comunicada
    MANUAL = "manual"  # creada a mano


# --- Flujo de estados (MAN-05) -----------------------------------------------

TRANSICIONES: dict[EstadoOT, frozenset[EstadoOT]] = {
    EstadoOT.ABIERTA: frozenset({EstadoOT.EN_CURSO, EstadoOT.CANCELADA}),
    EstadoOT.EN_CURSO: frozenset({EstadoOT.CERRADA, EstadoOT.CANCELADA}),
    EstadoOT.CERRADA: frozenset(),  # una OT cerrada es historial: no cambia
    EstadoOT.CANCELADA: frozenset(),
}

_NOMBRE = {
    EstadoOT.ABIERTA: "abierta",
    EstadoOT.EN_CURSO: "en curso",
    EstadoOT.CERRADA: "cerrada",
    EstadoOT.CANCELADA: "cancelada",
}


class TransicionNoValida(ValueError):
    """El cambio de estado no está permitido por el flujo."""


def comprobar_transicion(actual: EstadoOT, nuevo: EstadoOT) -> None:
    if nuevo not in TRANSICIONES[actual]:
        posibles = ", ".join(sorted(_NOMBRE[e] for e in TRANSICIONES[actual])) or "ninguno (es definitiva)"
        raise TransicionNoValida(
            f"Una OT {_NOMBRE[actual]} no puede pasar a {_NOMBRE[nuevo]}. Siguiente estado posible: {posibles}"
        )


def editable(estado: EstadoOT) -> bool:
    """Las líneas y los datos solo se cambian mientras la OT no está cerrada ni cancelada."""
    return estado in (EstadoOT.ABIERTA, EstadoOT.EN_CURSO)


# --- Coste (regla 4, MAN-06) -------------------------------------------------


class Concepto(StrEnum):
    MANO_OBRA = "mano_obra"  # cantidad = horas, precio = tarifa por hora
    RECAMBIO = "recambio"  # cantidad = unidades, precio = precio por unidad
    EXTERNO = "externo"  # trabajo de un taller externo: normalmente cantidad 1


_CENTIMO = Decimal("0.01")


def redondear(importe: Decimal) -> Decimal:
    """A céntimos, redondeando como se hace con el dinero (0,005 -> 0,01)."""
    return importe.quantize(_CENTIMO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Linea:
    concepto: Concepto
    cantidad: Decimal
    precio_unitario: Decimal

    @property
    def importe(self) -> Decimal:
        return redondear(self.cantidad * self.precio_unitario)


@dataclass(frozen=True)
class Coste:
    mano_obra: Decimal
    recambios: Decimal
    externos: Decimal

    @property
    def total(self) -> Decimal:
        return self.mano_obra + self.recambios + self.externos


def coste(lineas: Iterable[Linea]) -> Coste:
    """Coste de la OT: suma de sus líneas, desglosada por concepto (para los indicadores, MAN-08)."""
    por_concepto = {c: Decimal("0.00") for c in Concepto}
    for linea in lineas:
        por_concepto[linea.concepto] += linea.importe
    return Coste(
        mano_obra=por_concepto[Concepto.MANO_OBRA],
        recambios=por_concepto[Concepto.RECAMBIO],
        externos=por_concepto[Concepto.EXTERNO],
    )
