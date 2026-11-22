"""Cálculos de los indicadores de mantenimiento (MAN-08), en Python puro.

Criterio de la spec: "los valores del panel coinciden con un cálculo manual sobre
los datos de demostración". Por eso cada indicador tiene una definición exacta
(ver docstrings) que se puede reproducir a mano.
"""

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.reglas.km import Lectura


def km_recorridos(lecturas: Iterable[Lectura], desde: date, hasta: date) -> int:
    """Km recorridos en [desde, hasta].

    Final  = km de la última lectura con fecha <= hasta.
    Inicio = km de la última lectura con fecha <= desde; si no hay ninguna anterior,
             la primera lectura del periodo (el vehículo empezó a medirse dentro).
    Sin lecturas suficientes, 0.
    """
    ordenadas = sorted(lecturas, key=lambda l: (l.fecha, l.km))
    hasta_el_final = [l for l in ordenadas if l.fecha <= hasta]
    if not hasta_el_final:
        return 0
    antes_del_inicio = [l for l in hasta_el_final if l.fecha <= desde]
    inicio = antes_del_inicio[-1] if antes_del_inicio else next(l for l in hasta_el_final if l.fecha >= desde)
    return max(hasta_el_final[-1].km - inicio.km, 0)


def dias_cubiertos(intervalos: Iterable[tuple[date, date]], desde: date, hasta: date) -> int:
    """Días DISTINTOS cubiertos por los intervalos [inicio, fin] (ambos incluidos),
    recortados al periodo [desde, hasta]. Si dos intervalos se solapan, el día cuenta una vez.

    Se usa para los días de inmovilización: una avería y la OT que la repara pueden
    solaparse, y ese día el vehículo solo estuvo parado una vez.
    """
    recortados = sorted(
        (max(inicio, desde), min(fin, hasta)) for inicio, fin in intervalos if fin >= desde and inicio <= hasta
    )
    total = 0
    actual_inicio: date | None = None
    actual_fin: date | None = None
    for inicio, fin in recortados:
        if inicio > fin:
            continue
        if actual_fin is not None and inicio <= actual_fin + timedelta(days=1):
            actual_fin = max(actual_fin, fin)  # se solapa o es contiguo: se une
        else:
            if actual_inicio is not None and actual_fin is not None:
                total += (actual_fin - actual_inicio).days + 1
            actual_inicio, actual_fin = inicio, fin
    if actual_inicio is not None and actual_fin is not None:
        total += (actual_fin - actual_inicio).days + 1
    return total


def coste_por_km(coste: Decimal, km: int) -> Decimal | None:
    """€/km con 3 decimales (0,045 €/km). Sin km recorridos no tiene sentido: None."""
    if km <= 0:
        return None
    return (coste / Decimal(km)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def porcentaje(parte: Decimal | int, total: Decimal | int) -> Decimal | None:
    """Porcentaje con 1 decimal (76,2 %). Sin total, None."""
    if not total:
        return None
    return (Decimal(parte) * 100 / Decimal(total)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
