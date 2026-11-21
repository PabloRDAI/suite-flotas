"""Reglas de las lecturas de km (FLO-05).

"No se acepta una lectura menor que la anterior; los km actuales del vehículo
son los de la última lectura."

Como los km de un vehículo solo pueden subir con el tiempo, una lectura nueva
(aunque sea de una fecha pasada) tiene que encajar entre sus vecinas:
    km de la lectura anterior  <=  km nuevos  <=  km de la lectura posterior
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lectura:
    """Una lectura de km: qué día y cuántos km marcaba el vehículo."""

    fecha: date
    km: int


class LecturaNoValida(ValueError):
    """La lectura incumple una regla de negocio; el mensaje se muestra al usuario."""


def _fmt(fecha: date) -> str:
    return fecha.strftime("%d/%m/%Y")


def _fmt_km(km: int) -> str:
    return f"{km:,}".replace(",", ".")  # 120000 -> "120.000" (formato español)


def comprobar_lectura(nueva: Lectura, existentes: Iterable[Lectura], hoy: date) -> None:
    """Lanza LecturaNoValida si `nueva` no puede añadirse a las `existentes`.

    - La fecha no puede ser futura.
    - No puede tener menos km que ninguna lectura de su misma fecha o anterior.
    - No puede tener más km que ninguna lectura de fecha posterior.
    """
    if nueva.fecha > hoy:
        raise LecturaNoValida("La fecha de la lectura no puede ser futura")
    if nueva.km < 0:
        raise LecturaNoValida("Los km no pueden ser negativos")

    lecturas = list(existentes)
    anteriores = [l for l in lecturas if l.fecha <= nueva.fecha]
    posteriores = [l for l in lecturas if l.fecha > nueva.fecha]

    if anteriores:
        previa = max(anteriores, key=lambda l: (l.km, l.fecha))
        if nueva.km < previa.km:
            raise LecturaNoValida(
                f"Los km ({_fmt_km(nueva.km)}) no pueden ser menores que los de la lectura "
                f"anterior ({_fmt_km(previa.km)} km, del {_fmt(previa.fecha)})"
            )
    if posteriores:
        siguiente = min(posteriores, key=lambda l: (l.km, l.fecha))
        if nueva.km > siguiente.km:
            raise LecturaNoValida(
                f"Los km ({_fmt_km(nueva.km)}) no pueden ser mayores que los de una lectura "
                f"posterior ({_fmt_km(siguiente.km)} km, del {_fmt(siguiente.fecha)})"
            )


def km_actuales(lecturas: Iterable[Lectura]) -> int:
    """Km de la última lectura (la de fecha más reciente; si hay varias ese día, la mayor).

    Sin lecturas, 0.
    """
    ultima = max(lecturas, key=lambda l: (l.fecha, l.km), default=None)
    return ultima.km if ultima else 0
