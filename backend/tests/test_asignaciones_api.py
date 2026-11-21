"""Tests de asignaciones conductor-vehículo por la API (PER-03, PER-04).

PER-03: "Un vehículo tiene como máximo un conductor habitual a la vez; el historial
de asignaciones se conserva."
PER-04: "Si se asigna un conductor con el permiso o el CAP vencidos, el sistema avisa
(sin bloquear)."
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AplicaA, Asignacion, Centro, Puesto, RolUsuario, Vencimiento
from tests.fabricas import (
    cabeceras,
    crear_empresa,
    crear_persona,
    crear_tipo_vencimiento,
    crear_usuario,
    crear_vehiculo,
)

HOY = date.today()
AYER = HOY - timedelta(days=1)


def dia(n: int) -> str:
    return str(HOY + timedelta(days=n))


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa, "1111AAA")
    centro = db.get(Centro, vehiculo.centro_id)  # las personas, en el mismo centro que el vehículo
    return {
        "db": db,
        "empresa": empresa,
        "vehiculo": vehiculo,
        "ana": crear_persona(db, empresa, "Ana", Puesto.CONDUCTOR, centro),
        "luis": crear_persona(db, empresa, "Luis", Puesto.CONDUCTOR, centro),
        "mecanico": crear_persona(db, empresa, "Mario", Puesto.MECANICO, centro),
        "trafico": cabeceras(crear_usuario(db, empresa, "trafico@example.com", RolUsuario.TRAFICO)),
        "conductor": cabeceras(crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR)),
    }


def asignar(api: TestClient, e: dict, persona: str, **extra: Any) -> Any:
    datos = {"persona_id": e[persona].id, "vehiculo_id": e["vehiculo"].id, **extra}
    return api.post("/asignaciones", json=datos, headers=e["trafico"])


def historial(api: TestClient, e: dict) -> list[dict]:
    return api.get(f"/vehiculos/{e['vehiculo'].id}/asignaciones", headers=e["conductor"]).json()


# --- PER-03: un habitual a la vez --------------------------------------------


def test_asignar_un_conductor_habitual(api: TestClient, e: dict) -> None:
    respuesta = asignar(api, e, "ana")

    assert respuesta.status_code == 201
    a = respuesta.json()
    assert (a["persona_nombre"], a["matricula"], a["habitual"], a["vigente"]) == ("Ana", "1111AAA", True, True)
    assert a["desde"] == str(HOY)  # sin fecha: hoy
    assert a["hasta"] is None
    assert a["avisos"] == []


def test_un_segundo_habitual_a_la_vez_se_rechaza(api: TestClient, e: dict) -> None:
    """Criterio literal de PER-03."""
    asignar(api, e, "ana")

    respuesta = asignar(api, e, "luis")

    assert respuesta.status_code == 409
    assert "Ana" in respuesta.json()["detail"]


def test_una_temporal_puede_coincidir_con_la_habitual(api: TestClient, e: dict) -> None:
    asignar(api, e, "ana")

    respuesta = asignar(api, e, "luis", habitual=False, desde=dia(3), hasta=dia(5))

    assert respuesta.status_code == 201


def test_cambiar_de_conductor_conserva_el_historial(api: TestClient, e: dict) -> None:
    """Criterio de PER-03: se finaliza la asignación de Ana (termina ayer) y Luis empieza hoy."""
    ana = asignar(api, e, "ana", desde=dia(-30)).json()

    finalizada = api.post(f"/asignaciones/{ana['id']}/finalizar", json={}, headers=e["trafico"])
    luis = asignar(api, e, "luis")

    assert finalizada.status_code == 200
    assert finalizada.json()["hasta"] == str(AYER)
    assert finalizada.json()["vigente"] is False
    assert luis.status_code == 201
    # El historial conserva las dos, de la más reciente a la más antigua.
    assert [(a["persona_nombre"], a["vigente"]) for a in historial(api, e)] == [("Luis", True), ("Ana", False)]


def test_finalizar_una_asignacion_de_hoy_termina_hoy(api: TestClient, e: dict) -> None:
    ana = asignar(api, e, "ana").json()

    finalizada = api.post(f"/asignaciones/{ana['id']}/finalizar", json={}, headers=e["trafico"]).json()

    assert finalizada["hasta"] == str(HOY)


def test_finalizar_con_fecha_y_errores(api: TestClient, e: dict) -> None:
    ana = asignar(api, e, "ana", desde=dia(-10)).json()

    antes_de_empezar = api.post(f"/asignaciones/{ana['id']}/finalizar", json={"hasta": dia(-20)}, headers=e["trafico"])
    bien = api.post(f"/asignaciones/{ana['id']}/finalizar", json={"hasta": dia(-2)}, headers=e["trafico"])
    otra_vez = api.post(f"/asignaciones/{ana['id']}/finalizar", json={}, headers=e["trafico"])

    assert antes_de_empezar.status_code == 422
    assert bien.json()["hasta"] == dia(-2)
    assert otra_vez.status_code == 409  # ya tenía fecha de fin


def test_un_habitual_futuro_que_se_solapa_tambien_se_rechaza(api: TestClient, e: dict) -> None:
    asignar(api, e, "ana", desde=dia(-30), hasta=dia(10))

    assert asignar(api, e, "luis", desde=dia(5)).status_code == 409
    assert asignar(api, e, "luis", desde=dia(11)).status_code == 201


def test_la_base_de_datos_impide_dos_habituales_solapados(db: Session, e: dict) -> None:
    """Última barrera: aunque se salte la API, la restricción de exclusión lo impide."""
    comun = {"empresa_id": e["empresa"].id, "vehiculo_id": e["vehiculo"].id, "habitual": True}
    db.add(Asignacion(persona_id=e["ana"].id, desde=HOY - timedelta(days=10), **comun))
    db.flush()

    db.add(Asignacion(persona_id=e["luis"].id, desde=HOY, **comun))
    with pytest.raises(IntegrityError, match="ex_asignacion_un_habitual_a_la_vez"):
        db.flush()


# --- PER-04: aviso por documentación caducada (sin bloquear) ------------------


def test_avisa_si_el_cap_esta_caducado_pero_asigna_igual(api: TestClient, e: dict) -> None:
    """Criterio literal de PER-04."""
    db = e["db"]
    cap = crear_tipo_vencimiento(db, e["empresa"], "CAP", dias_aviso=60, aplica_a=AplicaA.PERSONA)
    db.add(Vencimiento(empresa_id=e["empresa"].id, persona_id=e["ana"].id, tipo_id=cap.id, fecha_caducidad=HOY - timedelta(days=3)))
    db.flush()

    respuesta = asignar(api, e, "ana")

    assert respuesta.status_code == 201  # no bloquea…
    assert len(respuesta.json()["avisos"]) == 1  # …pero avisa
    assert respuesta.json()["avisos"][0].startswith("CAP: caducó el")
    assert historial(api, e)[0]["avisos"] == respuesta.json()["avisos"]  # y el aviso sigue en el historial


def test_una_asignacion_terminada_no_avisa(api: TestClient, e: dict) -> None:
    """El historial no genera avisos: ya no importa."""
    db = e["db"]
    cap = crear_tipo_vencimiento(db, e["empresa"], "CAP", aplica_a=AplicaA.PERSONA)
    db.add(Vencimiento(empresa_id=e["empresa"].id, persona_id=e["ana"].id, tipo_id=cap.id, fecha_caducidad=HOY - timedelta(days=3)))
    db.flush()

    terminada = asignar(api, e, "ana", desde=dia(-60), hasta=dia(-30)).json()

    assert terminada["avisos"] == []


# --- Validaciones y permisos -------------------------------------------------


def test_solo_se_asignan_conductores(api: TestClient, e: dict) -> None:
    respuesta = asignar(api, e, "mecanico")

    assert respuesta.status_code == 422
    assert "Mario no tiene puesto de conductor/a" in respuesta.json()["detail"]


def test_no_se_asigna_una_persona_de_baja_ni_un_vehiculo_de_baja(api: TestClient, e: dict) -> None:
    api.delete(f"/personas/{e['luis'].id}", headers=e["trafico"])
    assert asignar(api, e, "luis").status_code == 422

    api.delete(f"/vehiculos/{e['vehiculo'].id}", headers=e["trafico"])
    assert asignar(api, e, "ana").status_code == 422


def test_fechas_al_reves_responden_422(api: TestClient, e: dict) -> None:
    assert asignar(api, e, "ana", desde=dia(5), hasta=dia(1)).status_code == 422
    assert asignar(api, e, "ana", hasta=dia(-1)).status_code == 422  # sin desde = hoy, y hasta es ayer


def test_no_se_mezclan_empresas(api: TestClient, e: dict) -> None:
    otra = crear_empresa(e["db"], "Otra")
    ajena = crear_persona(e["db"], otra, "Ajena")
    vehiculo_ajeno = crear_vehiculo(e["db"], otra, "9999ZZZ")

    persona_ajena = api.post("/asignaciones", json={"persona_id": ajena.id, "vehiculo_id": e["vehiculo"].id}, headers=e["trafico"])
    vehiculo_ajeno_r = api.post("/asignaciones", json={"persona_id": e["ana"].id, "vehiculo_id": vehiculo_ajeno.id}, headers=e["trafico"])

    assert persona_ajena.status_code == 422
    assert vehiculo_ajeno_r.status_code == 422
    assert api.get(f"/vehiculos/{vehiculo_ajeno.id}/asignaciones", headers=e["trafico"]).status_code == 404


def test_el_conductor_consulta_pero_no_asigna(api: TestClient, e: dict) -> None:
    datos = {"persona_id": e["ana"].id, "vehiculo_id": e["vehiculo"].id}

    assert api.post("/asignaciones", json=datos, headers=e["conductor"]).status_code == 403
    assert api.get(f"/personas/{e['ana'].id}/asignaciones", headers=e["conductor"]).status_code == 200


def test_historial_de_la_persona(api: TestClient, e: dict) -> None:
    otro = crear_vehiculo(e["db"], e["empresa"], "2222BBB")
    asignar(api, e, "ana", desde=dia(-100), hasta=dia(-50))
    api.post("/asignaciones", json={"persona_id": e["ana"].id, "vehiculo_id": otro.id, "desde": dia(-49)}, headers=e["trafico"])

    lista = api.get(f"/personas/{e['ana'].id}/asignaciones", headers=e["trafico"]).json()

    assert [(a["matricula"], a["vigente"]) for a in lista] == [("2222BBB", True), ("1111AAA", False)]


def test_borrar_una_asignacion_erronea(api: TestClient, e: dict) -> None:
    erronea = asignar(api, e, "ana").json()

    assert api.delete(f"/asignaciones/{erronea['id']}", headers=e["trafico"]).status_code == 204
    assert historial(api, e) == []
    assert api.delete(f"/asignaciones/{erronea['id']}", headers=e["trafico"]).status_code == 404
