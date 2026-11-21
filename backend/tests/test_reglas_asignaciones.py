"""Tests unitarios de las reglas de asignaciones (PER-03, PER-04). Sin base de datos."""

from datetime import date

import pytest

from app.reglas.asignaciones import (
    AsignacionExistente,
    AsignacionNoValida,
    Periodo,
    avisos_de_documentacion,
    comprobar_habitual,
    se_solapan,
)
from app.reglas.vencimientos import Documento


def d(mes: int, dia: int) -> date:
    return date(2026, mes, dia)


# --- Solapamiento de periodos (tabla de decisión) ----------------------------

CASOS_SOLAPE = [
    # (descripción, periodo A, periodo B, ¿se solapan?)
    ("A antes que B, sin tocarse", Periodo(d(1, 1), d(1, 31)), Periodo(d(2, 1), d(2, 28)), False),
    ("A termina el día que empieza B", Periodo(d(1, 1), d(2, 1)), Periodo(d(2, 1), d(2, 28)), True),
    ("B dentro de A", Periodo(d(1, 1), d(6, 30)), Periodo(d(3, 1), d(3, 31)), True),
    ("se cruzan", Periodo(d(1, 1), d(3, 31)), Periodo(d(3, 1), d(5, 31)), True),
    ("A sin fin, B después", Periodo(d(1, 1), None), Periodo(d(9, 1), d(9, 30)), True),
    ("A sin fin, B antes", Periodo(d(5, 1), None), Periodo(d(1, 1), d(4, 30)), False),
    ("los dos sin fin", Periodo(d(1, 1), None), Periodo(d(6, 1), None), True),
    ("mismo día", Periodo(d(3, 3), d(3, 3)), Periodo(d(3, 3), d(3, 3)), True),
]


@pytest.mark.parametrize(("a", "b", "esperado"), [c[1:] for c in CASOS_SOLAPE], ids=[c[0] for c in CASOS_SOLAPE])
def test_se_solapan(a: Periodo, b: Periodo, esperado: bool) -> None:
    assert se_solapan(a, b) is esperado
    assert se_solapan(b, a) is esperado  # es simétrico


def test_periodo_contiene() -> None:
    assert Periodo(d(1, 1), d(1, 31)).contiene(d(1, 31))
    assert not Periodo(d(1, 1), d(1, 31)).contiene(d(2, 1))
    assert Periodo(d(1, 1), None).contiene(d(12, 31))


# --- PER-03: un solo habitual a la vez ---------------------------------------

ANA_HABITUAL = AsignacionExistente("Ana", Periodo(d(1, 1), None), habitual=True)
EVA_TEMPORAL = AsignacionExistente("Eva", Periodo(d(3, 10), d(3, 20)), habitual=False)
LUIS_ANTERIOR = AsignacionExistente("Luis", Periodo(d(1, 1), d(5, 31)), habitual=True)


def test_un_segundo_habitual_que_se_solapa_se_rechaza() -> None:
    """Criterio literal de PER-03."""
    with pytest.raises(AsignacionNoValida, match="ya tiene como conductor/a habitual a Ana desde el 01/01/2026"):
        comprobar_habitual(Periodo(d(6, 1), None), True, [ANA_HABITUAL])


def test_el_mensaje_incluye_la_fecha_de_fin_si_la_tiene() -> None:
    with pytest.raises(AsignacionNoValida, match="hasta el 31/05/2026"):
        comprobar_habitual(Periodo(d(5, 1), None), True, [LUIS_ANTERIOR])


def test_un_habitual_que_empieza_cuando_termina_el_anterior_vale() -> None:
    """El historial: Luis fue habitual hasta el 31/05; el nuevo empieza el 01/06."""
    comprobar_habitual(Periodo(d(6, 1), None), True, [LUIS_ANTERIOR])


def test_una_temporal_puede_coincidir_con_la_habitual() -> None:
    comprobar_habitual(Periodo(d(3, 10), d(3, 20)), False, [ANA_HABITUAL])


def test_las_temporales_existentes_no_impiden_un_habitual() -> None:
    comprobar_habitual(Periodo(d(3, 1), None), True, [EVA_TEMPORAL])


# --- PER-04: avisos de documentación (no bloquean) ---------------------------


def doc(nombre: str, caduca: date, bloquea: bool = True, tipo_id: int = 1) -> Documento:
    return Documento(tipo_id, nombre, caduca, 30, bloquea)


def test_avisa_si_el_cap_esta_caducado() -> None:
    """Criterio de PER-04 (con un tipo que la empresa llamó "CAP")."""
    avisos = avisos_de_documentacion([doc("CAP", d(3, 1))], dia=d(3, 15))

    assert avisos == ["CAP: caducó el 01/03/2026"]


def test_avisa_de_todos_los_documentos_caducados() -> None:
    documentos = [doc("Permiso de conducir", d(2, 1), tipo_id=1), doc("CAP", d(3, 1), tipo_id=2)]

    assert len(avisos_de_documentacion(documentos, dia=d(3, 15))) == 2


def test_no_avisa_si_esta_en_regla_o_solo_en_ambar() -> None:
    documentos = [doc("CAP", d(3, 20), tipo_id=1), doc("Permiso de conducir", d(12, 31), tipo_id=2)]

    assert avisos_de_documentacion(documentos, dia=d(3, 15)) == []


def test_no_avisa_de_un_documento_ya_renovado() -> None:
    documentos = [doc("CAP", d(1, 1)), doc("CAP", d(12, 31))]  # el viejo es historial

    assert avisos_de_documentacion(documentos, dia=d(3, 15)) == []


def test_no_avisa_de_documentos_que_no_son_imprescindibles() -> None:
    assert avisos_de_documentacion([doc("Curso opcional", d(1, 1), bloquea=False)], dia=d(3, 15)) == []


def test_se_comprueba_en_el_dia_indicado() -> None:
    """Para una asignación futura, cuenta cómo estará la documentación el día que empieza."""
    cap = [doc("CAP", d(6, 30))]

    assert avisos_de_documentacion(cap, dia=d(3, 15)) == []  # hoy está en regla…
    assert avisos_de_documentacion(cap, dia=d(7, 1)) != []  # …pero el 1 de julio ya habrá caducado
