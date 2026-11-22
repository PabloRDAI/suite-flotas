"""Tests unitarios de los cálculos de indicadores (MAN-08). Sin base de datos.

Cada caso está pensado para poder comprobarse a mano.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.reglas.indicadores import coste_por_km, dias_cubiertos, km_recorridos, porcentaje
from app.reglas.km import Lectura


def d(mes: int, dia: int) -> date:
    return date(2026, mes, dia)


DESDE, HASTA = d(5, 1), d(10, 31)


# --- Km recorridos -----------------------------------------------------------


def test_km_recorridos_entre_la_lectura_anterior_al_inicio_y_la_ultima() -> None:
    lecturas = [Lectura(d(4, 20), 100_000), Lectura(d(6, 1), 104_000), Lectura(d(10, 15), 112_500), Lectura(d(11, 10), 115_000)]

    # Inicio: 20/04 (última antes del 01/05) = 100.000 · Final: 15/10 (última antes del 31/10) = 112.500
    assert km_recorridos(lecturas, DESDE, HASTA) == 12_500


def test_si_empezo_a_medirse_dentro_del_periodo_cuenta_desde_su_primera_lectura() -> None:
    lecturas = [Lectura(d(7, 1), 20_000), Lectura(d(9, 1), 26_000)]

    assert km_recorridos(lecturas, DESDE, HASTA) == 6_000


@pytest.mark.parametrize("lecturas", [[], [Lectura(d(11, 5), 50_000)]])
def test_sin_lecturas_en_el_periodo_son_cero_km(lecturas: list[Lectura]) -> None:
    assert km_recorridos(lecturas, DESDE, HASTA) == 0


def test_una_sola_lectura_anterior_son_cero_km() -> None:
    assert km_recorridos([Lectura(d(3, 1), 80_000)], DESDE, HASTA) == 0


# --- Días de inmovilización (unión de intervalos) ----------------------------


@pytest.mark.parametrize(
    ("intervalos", "dias"),
    [
        ([], 0),
        ([(d(6, 10), d(6, 10))], 1),  # un solo día: cuenta 1 (ambos extremos incluidos)
        ([(d(6, 10), d(6, 12))], 3),  # 10, 11 y 12
        ([(d(6, 10), d(6, 12)), (d(6, 20), d(6, 21))], 5),  # 3 + 2, sin solaparse
        ([(d(6, 10), d(6, 15)), (d(6, 13), d(6, 18))], 9),  # se solapan: del 10 al 18 = 9, no 6 + 6
        ([(d(6, 10), d(6, 12)), (d(6, 13), d(6, 14))], 5),  # contiguos: del 10 al 14
        ([(d(6, 10), d(6, 20)), (d(6, 12), d(6, 14))], 11),  # uno dentro de otro
        ([(d(4, 28), d(5, 2))], 2),  # empieza antes del periodo: solo cuentan el 1 y el 2 de mayo
        ([(d(10, 30), d(11, 5))], 2),  # termina después: solo el 30 y el 31 de octubre
        ([(d(3, 1), d(3, 31))], 0),  # fuera del periodo
    ],
)
def test_dias_cubiertos(intervalos: list[tuple[date, date]], dias: int) -> None:
    assert dias_cubiertos(intervalos, DESDE, HASTA) == dias


def test_el_orden_de_los_intervalos_no_importa() -> None:
    intervalos = [(d(6, 13), d(6, 18)), (d(6, 10), d(6, 15))]

    assert dias_cubiertos(intervalos, DESDE, HASTA) == dias_cubiertos(reversed(intervalos), DESDE, HASTA) == 9


# --- Coste por km y porcentajes ----------------------------------------------


def test_coste_por_km() -> None:
    assert coste_por_km(Decimal("562.50"), 12_500) == Decimal("0.045")  # 562,50 / 12.500
    assert coste_por_km(Decimal("100"), 3) == Decimal("33.333")


def test_sin_km_no_hay_coste_por_km() -> None:
    assert coste_por_km(Decimal("100"), 0) is None


def test_porcentaje() -> None:
    assert porcentaje(32, 42) == Decimal("76.2")  # 32 / 42 = 76,19… %
    assert porcentaje(Decimal("9748.00"), Decimal("12535.10")) == Decimal("77.8")
    assert porcentaje(0, 5) == Decimal("0.0")
    assert porcentaje(3, 0) is None


def test_un_intervalo_al_reves_se_ignora() -> None:
    """Defensa ante datos incoherentes (fin anterior al inicio): no suma días."""
    assert dias_cubiertos([(d(6, 15), d(6, 10)), (d(6, 20), d(6, 21))], DESDE, HASTA) == 2
