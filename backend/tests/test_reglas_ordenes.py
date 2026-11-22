"""Tests unitarios de las reglas de órdenes de trabajo (MAN-05, MAN-06). Sin base de datos."""

from decimal import Decimal

import pytest

from app.reglas.estado_vehiculo import EstadoOT
from app.reglas.ordenes import Concepto, Linea, TransicionNoValida, comprobar_transicion, coste, editable, redondear

D = Decimal  # para escribir importes de forma corta

ABIERTA, EN_CURSO, CERRADA, CANCELADA = EstadoOT.ABIERTA, EstadoOT.EN_CURSO, EstadoOT.CERRADA, EstadoOT.CANCELADA


# --- Flujo (MAN-05) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [(ABIERTA, EN_CURSO), (EN_CURSO, CERRADA), (ABIERTA, CANCELADA), (EN_CURSO, CANCELADA)],
)
def test_transiciones_permitidas(actual: EstadoOT, nuevo: EstadoOT) -> None:
    comprobar_transicion(actual, nuevo)  # no lanza excepción


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        (ABIERTA, CERRADA),  # hay que pasar por "en curso"
        (EN_CURSO, ABIERTA),  # no se vuelve atrás
        (CERRADA, EN_CURSO),  # una cerrada es definitiva
        (CERRADA, CANCELADA),
        (CANCELADA, ABIERTA),  # una cancelada también
        (ABIERTA, ABIERTA),
    ],
)
def test_transiciones_prohibidas(actual: EstadoOT, nuevo: EstadoOT) -> None:
    with pytest.raises(TransicionNoValida):
        comprobar_transicion(actual, nuevo)


def test_el_mensaje_dice_cual_es_el_siguiente_paso() -> None:
    with pytest.raises(TransicionNoValida, match="Una OT abierta no puede pasar a cerrada. Siguiente estado posible: cancelada, en curso"):
        comprobar_transicion(ABIERTA, CERRADA)


def test_solo_se_edita_mientras_no_esta_cerrada_ni_cancelada() -> None:
    assert editable(ABIERTA) and editable(EN_CURSO)
    assert not editable(CERRADA) and not editable(CANCELADA)


# --- Coste (regla 4, MAN-06) -------------------------------------------------


def test_el_total_es_la_suma_de_las_lineas() -> None:
    """Criterio literal de MAN-06."""
    lineas = [
        Linea(Concepto.MANO_OBRA, D("2.5"), D("45.00")),  # 2,5 h × 45 €/h = 112,50
        Linea(Concepto.RECAMBIO, D("1"), D("62.40")),  # aceite = 62,40
        Linea(Concepto.RECAMBIO, D("3"), D("14.95")),  # 3 filtros = 44,85
        Linea(Concepto.EXTERNO, D("1"), D("180.00")),  # taller externo = 180,00
    ]

    c = coste(lineas)

    assert c.total == D("399.75")
    assert c.total == sum(linea.importe for linea in lineas)


def test_el_coste_se_desglosa_por_concepto() -> None:
    """Para los indicadores de MAN-08: mano de obra, recambios y externos por separado."""
    c = coste([Linea(Concepto.MANO_OBRA, D("2"), D("40")), Linea(Concepto.RECAMBIO, D("2"), D("10.5")), Linea(Concepto.EXTERNO, D("1"), D("99.99"))])

    assert (c.mano_obra, c.recambios, c.externos) == (D("80.00"), D("21.00"), D("99.99"))


def test_una_ot_sin_lineas_cuesta_cero() -> None:
    assert coste([]).total == D("0.00")


def test_con_decimal_los_centimos_cuadran() -> None:
    """Con float, 0.1 + 0.2 = 0.30000000000000004. Con Decimal, 0.30 exacto."""
    c = coste([Linea(Concepto.RECAMBIO, D("1"), D("0.10")), Linea(Concepto.RECAMBIO, D("1"), D("0.20"))])

    assert c.total == D("0.30")
    assert 0.1 + 0.2 != 0.3  # el problema que evitamos


@pytest.mark.parametrize(
    ("importe", "esperado"),
    [(D("1.005"), D("1.01")), (D("1.004"), D("1.00")), (D("2.675"), D("2.68")), (D("10"), D("10.00"))],
)
def test_redondeo_a_centimos(importe: Decimal, esperado: Decimal) -> None:
    """Redondeo "comercial": 0,005 sube a 0,01 (con float, 2.675 se quedaría en 2.67)."""
    assert redondear(importe) == esperado


def test_el_importe_de_cada_linea_se_redondea_a_centimos() -> None:
    """1,5 h × 33,333 €/h = 49,9995 -> 50,00 €."""
    assert Linea(Concepto.MANO_OBRA, D("1.5"), D("33.333")).importe == D("50.00")
