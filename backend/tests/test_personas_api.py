"""Tests del personal (PER-01) y sus vencimientos (PER-02) por la API.

PER-01: "Alta, edición y baja lógica. Sin DNI ni datos bancarios en el MVP."
PER-02: "Mismas reglas de colores que FLO-06."
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AplicaA, Persona, RolUsuario, Vencimiento
from tests.fabricas import (
    cabeceras,
    crear_centro,
    crear_empresa,
    crear_persona,
    crear_tipo_vencimiento,
    crear_usuario,
    crear_vehiculo,
)

HOY = date.today()


def en(dias: int) -> str:
    return str(HOY + timedelta(days=dias))


@pytest.fixture
def entorno(db: Session) -> dict[str, Any]:
    empresa = crear_empresa(db)
    return {
        "db": db,
        "empresa": empresa,
        "centro": crear_centro(db, empresa, "Cochera"),
        "trafico": cabeceras(crear_usuario(db, empresa, "trafico@example.com", RolUsuario.TRAFICO)),
        "conductor": cabeceras(crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR)),
        "cap": crear_tipo_vencimiento(db, empresa, "CAP", dias_aviso=60, aplica_a=AplicaA.PERSONA).id,
        "carne": crear_tipo_vencimiento(db, empresa, "Permiso de conducir", dias_aviso=30, aplica_a=AplicaA.PERSONA).id,
        "itv": crear_tipo_vencimiento(db, empresa, "ITV", dias_aviso=30).id,
    }


def alta(api: TestClient, e: dict[str, Any], **cambios: Any) -> dict:
    datos = {"nombre": "Ana Conductora", "puesto": "conductor", "centro_id": e["centro"].id, "fecha_alta": "2024-03-01"}
    respuesta = api.post("/personas", json={**datos, **cambios}, headers=e["trafico"])
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- PER-01: ficha, privacidad y baja lógica ---------------------------------


def test_alta_consulta_y_listado(api: TestClient, entorno: dict) -> None:
    creada = alta(api, entorno)

    assert creada["activo"] is True
    assert creada["fecha_baja"] is None
    assert creada["semaforo"] == "verde"  # sin documentos
    assert api.get(f"/personas/{creada['id']}", headers=entorno["conductor"]).json() == creada
    assert [p["nombre"] for p in api.get("/personas", headers=entorno["conductor"]).json()] == ["Ana Conductora"]


@pytest.mark.parametrize("campo_prohibido", [{"dni": "12345678Z"}, {"iban": "ES0000000000000000000000"}, {"telefono": "600000000"}])
def test_no_se_admiten_datos_personales_no_previstos(api: TestClient, entorno: dict, campo_prohibido: dict) -> None:
    """Privacidad (PER-01 y RGPD): ni DNI ni datos bancarios. Cualquier campo no previsto -> 422."""
    datos = {"nombre": "X", "puesto": "conductor", "centro_id": entorno["centro"].id, "fecha_alta": "2024-03-01"}

    respuesta = api.post("/personas", json={**datos, **campo_prohibido}, headers=entorno["trafico"])

    assert respuesta.status_code == 422


def test_la_tabla_no_tiene_columnas_de_dni_ni_bancarias() -> None:
    """La protección más fuerte: los datos ni siquiera tienen dónde guardarse."""
    columnas = {c.name for c in Persona.__table__.columns}

    assert not columnas & {"dni", "nif", "nie", "iban", "cuenta_bancaria", "telefono", "direccion"}


def test_editar_solo_cambia_lo_enviado(api: TestClient, entorno: dict) -> None:
    creada = alta(api, entorno)

    editada = api.patch(f"/personas/{creada['id']}", json={"puesto": "trafico"}, headers=entorno["trafico"]).json()

    assert editada == {**creada, "puesto": "trafico"}


def test_la_baja_es_logica_y_guarda_la_fecha(api: TestClient, entorno: dict) -> None:
    creada = alta(api, entorno)

    assert api.delete(f"/personas/{creada['id']}", headers=entorno["trafico"]).status_code == 204

    ficha = api.get(f"/personas/{creada['id']}", headers=entorno["trafico"]).json()
    assert ficha["activo"] is False
    assert ficha["fecha_baja"] == str(HOY)
    assert api.get("/personas", headers=entorno["trafico"]).json() == []  # fuera del listado normal…
    assert len(api.get("/personas", params={"incluir_bajas": True}, headers=entorno["trafico"]).json()) == 1  # …pero existe
    # Una persona de baja no se edita ni se vuelve a dar de baja.
    assert api.patch(f"/personas/{creada['id']}", json={"nombre": "Y"}, headers=entorno["trafico"]).status_code == 404
    assert api.delete(f"/personas/{creada['id']}", headers=entorno["trafico"]).status_code == 404


def test_filtros_del_listado(api: TestClient, entorno: dict) -> None:
    otro_centro = crear_centro(entorno["db"], entorno["empresa"], "Taller")
    alta(api, entorno, nombre="Ana", puesto="conductor")
    alta(api, entorno, nombre="Bea", puesto="mecanico", centro_id=otro_centro.id)

    def nombres(**filtros: Any) -> list[str]:
        return [p["nombre"] for p in api.get("/personas", params=filtros, headers=entorno["trafico"]).json()]

    assert nombres() == ["Ana", "Bea"]
    assert nombres(puesto="mecanico") == ["Bea"]
    assert nombres(centro_id=otro_centro.id) == ["Bea"]


@pytest.mark.parametrize(
    "datos_invalidos",
    [{"nombre": "   "}, {"puesto": "piloto"}, {"fecha_alta": "no-es-fecha"}, {"centro_id": 999_999}],
)
def test_datos_invalidos_responden_422(api: TestClient, entorno: dict, datos_invalidos: dict) -> None:
    datos = {"nombre": "X", "puesto": "conductor", "centro_id": entorno["centro"].id, "fecha_alta": "2024-03-01"}

    assert api.post("/personas", json={**datos, **datos_invalidos}, headers=entorno["trafico"]).status_code == 422


def test_no_se_vacia_un_campo_obligatorio(api: TestClient, entorno: dict) -> None:
    creada = alta(api, entorno)

    assert api.patch(f"/personas/{creada['id']}", json={"nombre": None}, headers=entorno["trafico"]).status_code == 422


# --- Enlace con un usuario de la aplicación ----------------------------------


def test_enlazar_y_desenlazar_un_usuario(api: TestClient, entorno: dict) -> None:
    usuario = crear_usuario(entorno["db"], entorno["empresa"], "ana@example.com", RolUsuario.CONDUCTOR)
    creada = alta(api, entorno, usuario_id=usuario.id)
    assert creada["usuario_id"] == usuario.id

    desenlazada = api.patch(f"/personas/{creada['id']}", json={"usuario_id": None}, headers=entorno["trafico"])

    assert desenlazada.json()["usuario_id"] is None


def test_enlazar_al_editar_y_reenviar_el_mismo_usuario(api: TestClient, entorno: dict) -> None:
    """Enviar de nuevo el usuario que ya tiene enlazado no es un conflicto consigo misma."""
    usuario = crear_usuario(entorno["db"], entorno["empresa"], "ana@example.com", RolUsuario.CONDUCTOR)
    creada = alta(api, entorno)

    primera = api.patch(f"/personas/{creada['id']}", json={"usuario_id": usuario.id}, headers=entorno["trafico"])
    segunda = api.patch(f"/personas/{creada['id']}", json={"usuario_id": usuario.id}, headers=entorno["trafico"])

    assert primera.status_code == segunda.status_code == 200
    assert segunda.json()["usuario_id"] == usuario.id


def test_un_usuario_solo_puede_estar_enlazado_a_una_persona(api: TestClient, entorno: dict) -> None:
    usuario = crear_usuario(entorno["db"], entorno["empresa"], "ana@example.com", RolUsuario.CONDUCTOR)
    alta(api, entorno, nombre="Ana", usuario_id=usuario.id)

    datos = {"nombre": "Otra", "puesto": "conductor", "centro_id": entorno["centro"].id, "fecha_alta": "2024-03-01"}
    respuesta = api.post("/personas", json={**datos, "usuario_id": usuario.id}, headers=entorno["trafico"])

    assert respuesta.status_code == 409
    assert "Ana" in respuesta.json()["detail"]


def test_no_se_enlaza_un_usuario_de_otra_empresa(api: TestClient, entorno: dict) -> None:
    ajeno = crear_usuario(entorno["db"], crear_empresa(entorno["db"], "Otra"), "x@example.com")
    datos = {"nombre": "X", "puesto": "conductor", "centro_id": entorno["centro"].id, "fecha_alta": "2024-03-01"}

    respuesta = api.post("/personas", json={**datos, "usuario_id": ajeno.id}, headers=entorno["trafico"])

    assert respuesta.status_code == 422


# --- Permisos y aislamiento --------------------------------------------------


@pytest.mark.parametrize("rol", [RolUsuario.TALLER, RolUsuario.CONDUCTOR])
def test_taller_y_conductor_consultan_pero_no_gestionan(api: TestClient, entorno: dict, rol: RolUsuario) -> None:
    persona = crear_persona(entorno["db"], entorno["empresa"], centro=entorno["centro"])
    auth = cabeceras(crear_usuario(entorno["db"], entorno["empresa"], f"{rol}2@example.com", rol))
    datos = {"nombre": "X", "puesto": "conductor", "centro_id": entorno["centro"].id, "fecha_alta": "2024-03-01"}

    assert api.get("/personas", headers=auth).status_code == 200
    assert api.post("/personas", json=datos, headers=auth).status_code == 403
    assert api.patch(f"/personas/{persona.id}", json={"nombre": "Y"}, headers=auth).status_code == 403
    assert api.delete(f"/personas/{persona.id}", headers=auth).status_code == 403


def test_cada_empresa_solo_ve_su_personal(api: TestClient, entorno: dict) -> None:
    ajena = crear_persona(entorno["db"], crear_empresa(entorno["db"], "Otra"), "Persona ajena")
    alta(api, entorno)

    assert [p["nombre"] for p in api.get("/personas", headers=entorno["trafico"]).json()] == ["Ana Conductora"]
    assert api.get(f"/personas/{ajena.id}", headers=entorno["trafico"]).status_code == 404
    assert api.get(f"/personas/{ajena.id}/vencimientos", headers=entorno["trafico"]).status_code == 404


# --- PER-02: vencimientos de la persona --------------------------------------


def registrar(api: TestClient, e: dict, persona_id: int, tipo: str, dias: int) -> Any:
    return api.post(
        f"/personas/{persona_id}/vencimientos",
        json={"tipo_id": e[tipo], "fecha_caducidad": en(dias)},
        headers=e["trafico"],
    )


@pytest.mark.parametrize(("dias", "color"), [(-1, "rojo"), (0, "ambar"), (30, "ambar"), (31, "verde")])
def test_mismas_reglas_de_colores_que_los_vehiculos(api: TestClient, entorno: dict, dias: int, color: str) -> None:
    """Criterio literal de PER-02: el permiso (aviso 30) se comporta igual que la ITV en FLO-06."""
    persona = alta(api, entorno)

    venc = registrar(api, entorno, persona["id"], "carne", dias)

    assert venc.status_code == 201
    assert venc.json()["semaforo"] == color
    assert venc.json()["tipo_nombre"] == "Permiso de conducir"


def test_el_listado_muestra_el_peor_semaforo_de_cada_persona(api: TestClient, entorno: dict) -> None:
    ana = alta(api, entorno, nombre="Ana")
    bea = alta(api, entorno, nombre="Bea")
    registrar(api, entorno, ana["id"], "cap", 45)  # ámbar (aviso 60)
    registrar(api, entorno, ana["id"], "carne", 300)  # verde
    registrar(api, entorno, bea["id"], "cap", -2)  # rojo

    semaforos = {p["nombre"]: p["semaforo"] for p in api.get("/personas", headers=entorno["trafico"]).json()}

    assert semaforos == {"Ana": "ambar", "Bea": "rojo"}


def test_renovar_un_documento_pasa_el_anterior_a_historial(api: TestClient, entorno: dict) -> None:
    persona = alta(api, entorno)
    registrar(api, entorno, persona["id"], "cap", -5)
    registrar(api, entorno, persona["id"], "cap", 1800)

    lista = api.get(f"/personas/{persona['id']}/vencimientos", headers=entorno["trafico"]).json()

    assert [v["vigente"] for v in lista] == [False, True]
    assert api.get(f"/personas/{persona['id']}", headers=entorno["trafico"]).json()["semaforo"] == "verde"


def test_no_se_puede_usar_un_tipo_de_vehiculo_para_una_persona(api: TestClient, entorno: dict) -> None:
    persona = alta(api, entorno)

    respuesta = registrar(api, entorno, persona["id"], "itv", 100)

    assert respuesta.status_code == 422
    assert "vehículos" in respuesta.json()["detail"]


def test_el_conductor_consulta_pero_no_registra_documentos(api: TestClient, entorno: dict) -> None:
    persona = alta(api, entorno)

    respuesta = api.post(
        f"/personas/{persona['id']}/vencimientos",
        json={"tipo_id": entorno["cap"], "fecha_caducidad": en(100)},
        headers=entorno["conductor"],
    )

    assert respuesta.status_code == 403
    assert api.get(f"/personas/{persona['id']}/vencimientos", headers=entorno["conductor"]).status_code == 200


def test_borrar_un_vencimiento_de_persona(api: TestClient, entorno: dict) -> None:
    persona = alta(api, entorno)
    venc = registrar(api, entorno, persona["id"], "cap", -1).json()

    assert api.delete(f"/personas/{persona['id']}/vencimientos/{venc['id']}", headers=entorno["trafico"]).status_code == 204
    assert api.get(f"/personas/{persona['id']}", headers=entorno["trafico"]).json()["semaforo"] == "verde"
    assert api.delete(f"/personas/{persona['id']}/vencimientos/{venc['id']}", headers=entorno["trafico"]).status_code == 404


# --- Integridad en la base de datos ------------------------------------------


def test_un_vencimiento_tiene_exactamente_un_titular(db: Session, entorno: dict) -> None:
    """CHECK un_solo_titular: ni ninguno ni los dos (vehículo y persona a la vez)."""
    empresa = entorno["empresa"]
    vehiculo = crear_vehiculo(db, empresa)
    persona = crear_persona(db, empresa, centro=entorno["centro"])

    for titulares in ({}, {"vehiculo_id": vehiculo.id, "persona_id": persona.id}):
        # begin_nested(): savepoint propio. Al fallar, solo se deshace este intento
        # (el vehículo y la persona creados arriba siguen existiendo para el siguiente).
        with pytest.raises(IntegrityError, match="ck_vencimiento_un_solo_titular"), db.begin_nested():
            db.add(Vencimiento(empresa_id=empresa.id, tipo_id=entorno["cap"], fecha_caducidad=HOY, **titulares))
            db.flush()
        assert db.get(type(persona), persona.id) is not None


def test_una_persona_no_puede_estar_en_un_centro_de_otra_empresa(db: Session, entorno: dict) -> None:
    centro_ajeno = crear_centro(db, crear_empresa(db, "Otra"))

    db.add(Persona(empresa_id=entorno["empresa"].id, nombre="X", puesto="conductor", centro_id=centro_ajeno.id, fecha_alta=HOY))

    with pytest.raises(IntegrityError, match="fk_persona_centro_misma_empresa"):
        db.flush()


def test_borrar_una_persona_borra_sus_vencimientos(db: Session, entorno: dict) -> None:
    """ON DELETE CASCADE (solo para borrados reales; la API hace baja lógica)."""
    persona = crear_persona(db, entorno["empresa"], centro=entorno["centro"])
    db.add(Vencimiento(empresa_id=entorno["empresa"].id, persona_id=persona.id, tipo_id=entorno["cap"], fecha_caducidad=HOY))
    db.flush()

    db.delete(persona)
    db.flush()

    assert db.scalar(select(Vencimiento).where(Vencimiento.persona_id == persona.id)) is None
