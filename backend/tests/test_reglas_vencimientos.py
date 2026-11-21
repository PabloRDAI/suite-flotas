"""Tests unitarios de las reglas de vencimientos (FLO-06, FLO-07). Sin base de datos."""

from datetime import date, timedelta

import pytest

from app.reglas.vencimientos import (
    Documento,
    Semaforo,
    aptitud_para_salir,
    dias_restantes,
    peor,
    semaforo,
    vigentes,
)

HOY = date(2026, 11, 21)


def en(dias: int) -> date:
    """Fecha dentro de `dias` días (negativo: hace `dias` días)."""
    return HOY + timedelta(days=dias)


def doc(tipo_id: int, nombre: str, caduca: date, dias_aviso: int = 30, bloquea: bool = True) -> Documento:
    return Documento(tipo_id, nombre, caduca, dias_aviso, bloquea)


ITV, SEGURO, EXTINTORES = 1, 2, 3


# --- Semáforo (regla 2 del motor) --------------------------------------------


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (-365, Semaforo.ROJO),  # caducado hace un año
        (-1, Semaforo.ROJO),  # caducó ayer
        (0, Semaforo.AMBAR),  # caduca hoy: todavía es válido hoy
        (1, Semaforo.AMBAR),
        (30, Semaforo.AMBAR),  # justo en el límite del aviso: "quedan ≤ 30"
        (31, Semaforo.VERDE),  # un día fuera del aviso
        (400, Semaforo.VERDE),
    ],
)
def test_semaforo_con_30_dias_de_aviso(dias: int, esperado: Semaforo) -> None:
    """Criterio de FLO-06: "a ≤ 30 días aparece en ámbar y uno vencido en rojo"."""
    assert semaforo(en(dias), dias_aviso=30, hoy=HOY) == esperado


def test_el_plazo_de_aviso_es_configurable_por_tipo() -> None:
    """Criterio de FLO-06: la misma fecha da colores distintos según el aviso del tipo."""
    caduca_en_45_dias = en(45)

    assert semaforo(caduca_en_45_dias, dias_aviso=30, hoy=HOY) == Semaforo.VERDE
    assert semaforo(caduca_en_45_dias, dias_aviso=60, hoy=HOY) == Semaforo.AMBAR


def test_sin_aviso_solo_es_ambar_el_dia_que_caduca() -> None:
    assert semaforo(en(0), dias_aviso=0, hoy=HOY) == Semaforo.AMBAR
    assert semaforo(en(1), dias_aviso=0, hoy=HOY) == Semaforo.VERDE


def test_dias_restantes() -> None:
    assert dias_restantes(en(10), HOY) == 10
    assert dias_restantes(en(0), HOY) == 0
    assert dias_restantes(en(-3), HOY) == -3


def test_peor_semaforo() -> None:
    assert peor([Semaforo.VERDE, Semaforo.ROJO, Semaforo.AMBAR]) == Semaforo.ROJO
    assert peor([Semaforo.VERDE, Semaforo.AMBAR]) == Semaforo.AMBAR
    assert peor([]) == Semaforo.VERDE


# --- Documentos vigentes -----------------------------------------------------


def test_de_cada_tipo_solo_cuenta_el_que_caduca_mas_tarde() -> None:
    """Al renovar la ITV, la antigua (vencida) pasa a ser historial."""
    itv_antigua = doc(ITV, "ITV", en(-100))
    itv_renovada = doc(ITV, "ITV", en(265))
    seguro = doc(SEGURO, "Seguro", en(50))

    assert vigentes([itv_antigua, seguro, itv_renovada]) == [seguro, itv_renovada]


# --- Apto para salir (FLO-07) ------------------------------------------------


def test_con_la_itv_vencida_no_es_apto_aunque_este_operativo() -> None:
    """Criterio de aceptación literal de FLO-07."""
    resultado = aptitud_para_salir(True, "operativo", [doc(ITV, "ITV", en(-1))], HOY)

    assert resultado.apto is False
    assert resultado.motivos == ["ITV: caducó el 20/11/2026"]
    assert resultado.semaforo == Semaforo.ROJO


def test_con_todo_en_regla_es_apto() -> None:
    resultado = aptitud_para_salir(True, "operativo", [doc(ITV, "ITV", en(200)), doc(SEGURO, "Seguro", en(90))], HOY)

    assert resultado.apto is True
    assert resultado.motivos == []
    assert resultado.semaforo == Semaforo.VERDE


def test_un_documento_en_ambar_avisa_pero_no_impide_salir() -> None:
    resultado = aptitud_para_salir(True, "operativo", [doc(ITV, "ITV", en(10))], HOY)

    assert resultado.apto is True
    assert resultado.semaforo == Semaforo.AMBAR


def test_una_itv_vencida_pero_ya_renovada_no_impide_salir() -> None:
    documentos = [doc(ITV, "ITV", en(-100)), doc(ITV, "ITV", en(265))]

    assert aptitud_para_salir(True, "operativo", documentos, HOY).apto is True


def test_un_tipo_que_no_bloquea_la_salida_solo_avisa() -> None:
    """Configurable por la empresa: p. ej. una revisión interna que vigilan sin bloquear."""
    resultado = aptitud_para_salir(True, "operativo", [doc(EXTINTORES, "Extintores", en(-5), bloquea=False)], HOY)

    assert resultado.apto is True
    assert resultado.semaforo == Semaforo.ROJO  # pero sigue saliendo en rojo


@pytest.mark.parametrize("estado", ["en_taller", "inmovilizado"])
def test_un_vehiculo_que_no_esta_operativo_no_es_apto(estado: str) -> None:
    resultado = aptitud_para_salir(True, estado, [], HOY)

    assert resultado.apto is False
    assert resultado.motivos[0].startswith("Estado:")


def test_un_vehiculo_de_baja_no_es_apto() -> None:
    resultado = aptitud_para_salir(False, "baja", [], HOY)

    assert resultado.apto is False
    assert resultado.motivos == ["El vehículo está dado de baja"]


def test_se_listan_todos_los_motivos() -> None:
    documentos = [doc(ITV, "ITV", en(-1)), doc(SEGURO, "Seguro", en(-30))]

    resultado = aptitud_para_salir(True, "en_taller", documentos, HOY)

    assert len(resultado.motivos) == 3  # estado + ITV + seguro
