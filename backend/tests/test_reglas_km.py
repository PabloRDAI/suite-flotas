"""Tests unitarios de la regla de lecturas de km (FLO-05). Sin base de datos."""

from datetime import date

import pytest

from app.reglas.km import Lectura, LecturaNoValida, comprobar_lectura, km_actuales

HOY = date(2026, 11, 21)
LUNES, MIERCOLES, VIERNES = date(2026, 11, 16), date(2026, 11, 18), date(2026, 11, 20)

# Historial de ejemplo: 100.000 el lunes y 100.500 el viernes.
HISTORIAL = [Lectura(LUNES, 100_000), Lectura(VIERNES, 100_500)]


def test_la_primera_lectura_siempre_vale() -> None:
    comprobar_lectura(Lectura(HOY, 0), [], HOY)
    comprobar_lectura(Lectura(HOY, 250_000), [], HOY)


def test_una_lectura_mayor_que_la_anterior_vale() -> None:
    comprobar_lectura(Lectura(HOY, 100_600), HISTORIAL, HOY)


def test_una_lectura_igual_a_la_anterior_vale() -> None:
    """El vehículo puede no haberse movido."""
    comprobar_lectura(Lectura(HOY, 100_500), HISTORIAL, HOY)


def test_una_lectura_menor_que_la_anterior_se_rechaza() -> None:
    """Criterio de aceptación literal de FLO-05."""
    with pytest.raises(LecturaNoValida, match=r"menores que los de la lectura anterior \(100\.500 km, del 20/11/2026\)"):
        comprobar_lectura(Lectura(HOY, 100_499), HISTORIAL, HOY)


def test_una_lectura_atrasada_que_encaja_entre_sus_vecinas_vale() -> None:
    """Registrar hoy los km del miércoles: debe quedar entre el lunes y el viernes."""
    comprobar_lectura(Lectura(MIERCOLES, 100_200), HISTORIAL, HOY)


def test_una_lectura_atrasada_mayor_que_una_posterior_se_rechaza() -> None:
    with pytest.raises(LecturaNoValida, match="mayores que los de una lectura posterior"):
        comprobar_lectura(Lectura(MIERCOLES, 100_600), HISTORIAL, HOY)


def test_una_lectura_atrasada_menor_que_una_anterior_se_rechaza() -> None:
    with pytest.raises(LecturaNoValida, match="menores que los de la lectura anterior"):
        comprobar_lectura(Lectura(MIERCOLES, 99_000), HISTORIAL, HOY)


def test_el_mismo_dia_cuenta_como_anterior() -> None:
    """Dos lecturas el mismo día: la nueva es posterior, no puede ser menor."""
    with pytest.raises(LecturaNoValida):
        comprobar_lectura(Lectura(VIERNES, 100_400), HISTORIAL, HOY)


def test_una_fecha_futura_se_rechaza() -> None:
    with pytest.raises(LecturaNoValida, match="futura"):
        comprobar_lectura(Lectura(date(2026, 11, 22), 100_600), HISTORIAL, HOY)


def test_km_negativos_se_rechazan() -> None:
    with pytest.raises(LecturaNoValida, match="negativos"):
        comprobar_lectura(Lectura(HOY, -1), [], HOY)


def test_km_actuales_son_los_de_la_ultima_lectura() -> None:
    """Criterio de aceptación literal de FLO-05."""
    assert km_actuales(HISTORIAL) == 100_500
    # El orden en que llegan no importa: manda la fecha.
    assert km_actuales(reversed(HISTORIAL)) == 100_500
    # Una lectura atrasada no cambia los km actuales.
    assert km_actuales([*HISTORIAL, Lectura(MIERCOLES, 100_200)]) == 100_500


def test_sin_lecturas_los_km_actuales_son_cero() -> None:
    assert km_actuales([]) == 0
