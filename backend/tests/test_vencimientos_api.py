"""Tests de vencimientos de vehículo (FLO-06) y "apto para salir" (FLO-07) por la API.

Las reglas (semáforo, vigentes, aptitud) se prueban a fondo en
test_reglas_vencimientos.py; aquí se comprueba que la API las aplica.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AplicaA, EstadoVehiculo, RolUsuario
from tests.fabricas import cabeceras, crear_empresa, crear_tipo_vencimiento, crear_usuario, crear_vehiculo

HOY = date.today()


def en(dias: int) -> str:
    return str(HOY + timedelta(days=dias))


@pytest.fixture
def flota(db: Session) -> dict:
    """Empresa con un vehículo operativo, tipos ITV (30 días) y Seguro (60 días), y usuarios."""
    empresa = crear_empresa(db)
    return {
        "db": db,
        "empresa": empresa,
        "vehiculo": crear_vehiculo(db, empresa),
        "itv": crear_tipo_vencimiento(db, empresa, "ITV", dias_aviso=30).id,
        "seguro": crear_tipo_vencimiento(db, empresa, "Seguro", dias_aviso=60).id,
        "trafico": cabeceras(crear_usuario(db, empresa, "trafico@example.com", RolUsuario.TRAFICO)),
        "conductor": cabeceras(crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR)),
    }


def registrar(api: TestClient, flota: dict, tipo: str, dias: int) -> dict:
    respuesta = api.post(
        f"/vehiculos/{flota['vehiculo'].id}/vencimientos",
        json={"tipo_id": flota[tipo], "fecha_caducidad": en(dias)},
        headers=flota["trafico"],
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def aptitud(api: TestClient, flota: dict) -> dict:
    return api.get(f"/vehiculos/{flota['vehiculo'].id}/aptitud", headers=flota["conductor"]).json()


# --- FLO-06: semáforo --------------------------------------------------------


@pytest.mark.parametrize(("dias", "color"), [(-1, "rojo"), (0, "ambar"), (30, "ambar"), (31, "verde")])
def test_el_semaforo_llega_calculado_en_la_api(api: TestClient, flota: dict, dias: int, color: str) -> None:
    """Criterio de FLO-06: "a ≤ 30 días aparece en ámbar y uno vencido en rojo"."""
    venc = registrar(api, flota, "itv", dias)

    assert venc["semaforo"] == color
    assert venc["dias_restantes"] == dias
    assert venc["tipo_nombre"] == "ITV"
    assert venc["vigente"] is True


def test_el_plazo_de_aviso_es_el_de_cada_tipo(api: TestClient, flota: dict) -> None:
    """Criterio de FLO-06: a 45 días, la ITV (aviso 30) es verde y el seguro (aviso 60) ámbar."""
    assert registrar(api, flota, "itv", 45)["semaforo"] == "verde"
    assert registrar(api, flota, "seguro", 45)["semaforo"] == "ambar"


def test_al_renovar_el_anterior_pasa_a_historial(api: TestClient, flota: dict) -> None:
    antigua = registrar(api, flota, "itv", -10)
    renovada = registrar(api, flota, "itv", 355)

    lista = api.get(f"/vehiculos/{flota['vehiculo'].id}/vencimientos", headers=flota["conductor"]).json()

    vigente = {v["id"]: v["vigente"] for v in lista}
    assert vigente == {antigua["id"]: False, renovada["id"]: True}
    assert [v["id"] for v in lista] == [antigua["id"], renovada["id"]]  # del que caduca antes al de después


# --- FLO-07: apto para salir -------------------------------------------------


def test_con_la_itv_vencida_no_es_apto_aunque_este_operativo(api: TestClient, flota: dict) -> None:
    """Criterio de aceptación literal de FLO-07."""
    registrar(api, flota, "itv", -1)
    registrar(api, flota, "seguro", 200)

    resultado = aptitud(api, flota)

    assert flota["vehiculo"].estado == EstadoVehiculo.OPERATIVO
    assert resultado["apto"] is False
    assert resultado["semaforo"] == "rojo"
    assert len(resultado["motivos"]) == 1
    assert resultado["motivos"][0].startswith("ITV caducada el")


def test_tras_renovar_la_itv_vuelve_a_ser_apto(api: TestClient, flota: dict) -> None:
    registrar(api, flota, "itv", -1)
    assert aptitud(api, flota)["apto"] is False

    registrar(api, flota, "itv", 364)

    assert aptitud(api, flota) == {"apto": True, "motivos": [], "semaforo": "verde"}


def test_un_tipo_que_no_bloquea_solo_avisa(api: TestClient, flota: dict) -> None:
    tipo = crear_tipo_vencimiento(flota["db"], flota["empresa"], "Revisión interna", bloquea_salida=False)
    flota["revision"] = tipo.id
    registrar(api, flota, "revision", -3)

    resultado = aptitud(api, flota)

    assert resultado["apto"] is True
    assert resultado["semaforo"] == "rojo"


def test_un_vehiculo_sin_documentos_es_apto_si_esta_operativo(api: TestClient, flota: dict) -> None:
    assert aptitud(api, flota) == {"apto": True, "motivos": [], "semaforo": "verde"}


def test_un_vehiculo_en_taller_no_es_apto(api: TestClient, flota: dict) -> None:
    flota["vehiculo"].estado = EstadoVehiculo.EN_TALLER
    flota["db"].flush()

    resultado = aptitud(api, flota)

    assert resultado["apto"] is False
    assert resultado["motivos"] == ["Estado: en taller"]


# --- Validaciones y permisos -------------------------------------------------


def test_no_se_puede_usar_un_tipo_para_personas(api: TestClient, flota: dict) -> None:
    cap = crear_tipo_vencimiento(flota["db"], flota["empresa"], "CAP", aplica_a=AplicaA.PERSONA)

    respuesta = api.post(
        f"/vehiculos/{flota['vehiculo'].id}/vencimientos",
        json={"tipo_id": cap.id, "fecha_caducidad": en(100)},
        headers=flota["trafico"],
    )

    assert respuesta.status_code == 422
    assert "personas" in respuesta.json()["detail"]


def test_no_se_puede_usar_un_tipo_de_otra_empresa(api: TestClient, flota: dict) -> None:
    ajeno = crear_tipo_vencimiento(flota["db"], crear_empresa(flota["db"], "Otra empresa"), "ITV ajena")

    respuesta = api.post(
        f"/vehiculos/{flota['vehiculo'].id}/vencimientos",
        json={"tipo_id": ajeno.id, "fecha_caducidad": en(100)},
        headers=flota["trafico"],
    )

    assert respuesta.status_code == 422


def test_vehiculo_de_otra_empresa_responde_404(api: TestClient, flota: dict) -> None:
    ajeno = crear_vehiculo(flota["db"], crear_empresa(flota["db"], "Otra empresa"))

    assert api.get(f"/vehiculos/{ajeno.id}/vencimientos", headers=flota["trafico"]).status_code == 404
    assert api.get(f"/vehiculos/{ajeno.id}/aptitud", headers=flota["trafico"]).status_code == 404
    respuesta = api.post(
        f"/vehiculos/{ajeno.id}/vencimientos",
        json={"tipo_id": flota["itv"], "fecha_caducidad": en(100)},
        headers=flota["trafico"],
    )
    assert respuesta.status_code == 404


def test_el_conductor_consulta_pero_no_registra(api: TestClient, flota: dict) -> None:
    respuesta = api.post(
        f"/vehiculos/{flota['vehiculo'].id}/vencimientos",
        json={"tipo_id": flota["itv"], "fecha_caducidad": en(100)},
        headers=flota["conductor"],
    )

    assert respuesta.status_code == 403
    assert api.get(f"/vehiculos/{flota['vehiculo'].id}/vencimientos", headers=flota["conductor"]).status_code == 200


def test_borrar_un_vencimiento_registrado_por_error(api: TestClient, flota: dict) -> None:
    erroneo = registrar(api, flota, "itv", -1)
    assert aptitud(api, flota)["apto"] is False

    respuesta = api.delete(f"/vehiculos/{flota['vehiculo'].id}/vencimientos/{erroneo['id']}", headers=flota["trafico"])

    assert respuesta.status_code == 204
    assert aptitud(api, flota)["apto"] is True
    # Borrarlo otra vez: ya no existe.
    segundo = api.delete(f"/vehiculos/{flota['vehiculo'].id}/vencimientos/{erroneo['id']}", headers=flota["trafico"])
    assert segundo.status_code == 404


def test_filtrar_tipos_por_a_quien_aplican(api: TestClient, flota: dict) -> None:
    crear_tipo_vencimiento(flota["db"], flota["empresa"], "CAP", aplica_a=AplicaA.PERSONA)

    de_vehiculo = api.get("/tipos-vencimiento", params={"aplica_a": "vehiculo"}, headers=flota["trafico"]).json()
    de_persona = api.get("/tipos-vencimiento", params={"aplica_a": "persona"}, headers=flota["trafico"]).json()

    assert [t["nombre"] for t in de_vehiculo] == ["ITV", "Seguro"]
    assert [t["nombre"] for t in de_persona] == ["CAP"]
