"""Tests unitarios del motor de estado del vehículo (regla 1, FLO-03). Sin base de datos.

La regla se prueba con una TABLA DE DECISIÓN: cada fila es un caso con sus
entradas y el estado esperado.
"""

import pytest

from app.reglas.estado_vehiculo import (
    EstadoAveria,
    EstadoOT,
    EstadoVehiculo,
    GravedadAveria,
    ResumenAveria,
    ResumenOT,
    calcular_estado,
)

# --- Piezas para escribir los casos de forma corta ---------------------------

OT_ABIERTA_INMOVILIZA = ResumenOT(EstadoOT.ABIERTA, inmoviliza=True)
OT_EN_CURSO_INMOVILIZA = ResumenOT(EstadoOT.EN_CURSO, inmoviliza=True)
OT_CERRADA_INMOVILIZA = ResumenOT(EstadoOT.CERRADA, inmoviliza=True)
OT_CANCELADA_INMOVILIZA = ResumenOT(EstadoOT.CANCELADA, inmoviliza=True)
OT_ABIERTA_NO_INMOVILIZA = ResumenOT(EstadoOT.ABIERTA, inmoviliza=False)

AVERIA_INMOVILIZA_SIN_OT = ResumenAveria(GravedadAveria.INMOVILIZA, EstadoAveria.COMUNICADA, con_ot_abierta=False)
AVERIA_INMOVILIZA_CON_OT = ResumenAveria(GravedadAveria.INMOVILIZA, EstadoAveria.EN_REPARACION, con_ot_abierta=True)
# Tenía OT, pero se canceló: vuelve a estar "sin OT".
AVERIA_INMOVILIZA_OT_CANCELADA = ResumenAveria(
    GravedadAveria.INMOVILIZA, EstadoAveria.EN_REPARACION, con_ot_abierta=False
)
AVERIA_INMOVILIZA_RESUELTA = ResumenAveria(GravedadAveria.INMOVILIZA, EstadoAveria.RESUELTA, con_ot_abierta=False)
AVERIA_GRAVE_SIN_OT = ResumenAveria(GravedadAveria.GRAVE, EstadoAveria.COMUNICADA, con_ot_abierta=False)
AVERIA_LEVE_SIN_OT = ResumenAveria(GravedadAveria.LEVE, EstadoAveria.COMUNICADA, con_ot_abierta=False)

OPERATIVO, EN_TALLER, INMOVILIZADO, BAJA = (
    EstadoVehiculo.OPERATIVO,
    EstadoVehiculo.EN_TALLER,
    EstadoVehiculo.INMOVILIZADO,
    EstadoVehiculo.BAJA,
)

# --- Tabla de decisión -------------------------------------------------------
#   (descripción, activo, órdenes de trabajo, averías, estado esperado)
CASOS = [
    # Sin nada pendiente
    ("sin OT ni averías", True, [], [], OPERATIVO),
    # 1. De baja: manda sobre todo lo demás
    ("inactivo", False, [], [], BAJA),
    ("inactivo aunque tenga OT inmovilizante", False, [OT_ABIERTA_INMOVILIZA], [], BAJA),
    ("inactivo aunque tenga avería inmovilizante", False, [], [AVERIA_INMOVILIZA_SIN_OT], BAJA),
    # 2. En taller: OT abierta (o en curso) que inmoviliza
    ("OT abierta que inmoviliza", True, [OT_ABIERTA_INMOVILIZA], [], EN_TALLER),
    ("OT en curso que inmoviliza", True, [OT_EN_CURSO_INMOVILIZA], [], EN_TALLER),
    ("OT abierta que NO inmoviliza", True, [OT_ABIERTA_NO_INMOVILIZA], [], OPERATIVO),
    ("OT inmovilizante ya cerrada", True, [OT_CERRADA_INMOVILIZA], [], OPERATIVO),
    ("OT inmovilizante cancelada", True, [OT_CANCELADA_INMOVILIZA], [], OPERATIVO),
    ("varias OT, una abierta inmovilizante", True, [OT_CERRADA_INMOVILIZA, OT_EN_CURSO_INMOVILIZA], [], EN_TALLER),
    # 3. Inmovilizado: avería "inmoviliza" sin OT abierta
    ("avería inmovilizante sin OT", True, [], [AVERIA_INMOVILIZA_SIN_OT], INMOVILIZADO),
    ("avería inmovilizante cuya OT se canceló", True, [], [AVERIA_INMOVILIZA_OT_CANCELADA], INMOVILIZADO),
    ("avería inmovilizante ya resuelta", True, [], [AVERIA_INMOVILIZA_RESUELTA], OPERATIVO),
    ("avería grave sin OT", True, [], [AVERIA_GRAVE_SIN_OT], OPERATIVO),
    ("avería leve sin OT", True, [], [AVERIA_LEVE_SIN_OT], OPERATIVO),
    # Prioridades entre reglas
    ("avería inmovilizante con su OT inmovilizante abierta", True, [OT_ABIERTA_INMOVILIZA], [AVERIA_INMOVILIZA_CON_OT], EN_TALLER),
    ("OT inmovilizante y otra avería inmovilizante sin OT", True, [OT_ABIERTA_INMOVILIZA], [AVERIA_INMOVILIZA_SIN_OT], EN_TALLER),
]


@pytest.mark.parametrize(
    ("activo", "ordenes", "averias", "esperado"),
    [caso[1:] for caso in CASOS],
    ids=[caso[0] for caso in CASOS],  # el nombre de cada caso aparece en el informe de pytest
)
def test_regla_1_estado_del_vehiculo(
    activo: bool, ordenes: list[ResumenOT], averias: list[ResumenAveria], esperado: EstadoVehiculo
) -> None:
    assert calcular_estado(activo, ordenes, averias) == esperado


def test_flo_03_abrir_y_cerrar_una_ot_inmovilizante() -> None:
    """Criterio literal de FLO-03: con la OT abierta "en taller"; al cerrarla, "operativo"."""
    assert calcular_estado(True, [ResumenOT(EstadoOT.ABIERTA, inmoviliza=True)], []) == EN_TALLER
    assert calcular_estado(True, [ResumenOT(EstadoOT.CERRADA, inmoviliza=True)], []) == OPERATIVO


def test_acepta_cualquier_iterable() -> None:
    """Las listas pueden llegar como generadores (p. ej. directamente de una consulta)."""
    ordenes = (ot for ot in [OT_ABIERTA_INMOVILIZA])

    assert calcular_estado(True, ordenes, iter([])) == EN_TALLER
