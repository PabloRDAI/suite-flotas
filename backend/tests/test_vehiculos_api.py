"""Tests del CRUD de vehículos por la API (FLO-01).

Criterio de aceptación: "Alta, edición y baja lógica; la matrícula es única
dentro de la empresa".
"""

import itertools
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Empresa, RolUsuario
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, crear_vehiculo


_contador = itertools.count(1)


def datos_alta(empresa_db: tuple[Session, Empresa], **cambios: Any) -> dict[str, Any]:
    """JSON válido para dar de alta un vehículo (crea un centro y un tipo nuevos de la empresa)."""
    db, empresa = empresa_db
    n = next(_contador)  # para que los nombres de centro y tipo no se repitan
    datos: dict[str, Any] = {
        "matricula": "1234ABC",
        "centro_id": crear_centro(db, empresa, f"Centro {n}").id,
        "tipo_id": crear_tipo(db, empresa, f"Tipo {n}").id,
        "marca": "Marca Ficticia",
        "modelo": "Modelo X",
        "anio": 2020,
        "capacidad": 55,
        "combustible": "diesel",
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def entorno(db: Session) -> tuple[Session, Empresa, dict[str, str]]:
    """Una empresa con un usuario de tráfico (puede gestionar la flota) y su cabecera."""
    empresa = crear_empresa(db)
    trafico = crear_usuario(db, empresa, "trafico@example.com", RolUsuario.TRAFICO)
    return db, empresa, cabeceras(trafico)


# --- Alta --------------------------------------------------------------------


def test_alta_de_vehiculo(api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]) -> None:
    db, empresa, auth = entorno

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=auth)

    assert respuesta.status_code == 201
    vehiculo = respuesta.json()
    assert vehiculo["id"] > 0
    assert vehiculo["matricula"] == "1234ABC"
    assert vehiculo["estado"] == "operativo"
    assert vehiculo["km_actuales"] == 0
    assert vehiculo["activo"] is True
    # Y se puede consultar después.
    assert api.get(f"/vehiculos/{vehiculo['id']}", headers=auth).json() == vehiculo


@pytest.mark.parametrize("escrita", ["1234 abc", "1234-ABC", " 1234abc "])
def test_la_matricula_se_normaliza(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]], escrita: str
) -> None:
    db, empresa, auth = entorno

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), matricula=escrita), headers=auth)

    assert respuesta.status_code == 201
    assert respuesta.json()["matricula"] == "1234ABC"


def test_matricula_repetida_en_la_empresa_responde_409(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    """FLO-01. Escrita de otra forma ("1234-abc") sigue siendo la misma matrícula."""
    db, empresa, auth = entorno
    api.post("/vehiculos", json=datos_alta((db, empresa), matricula="1234ABC"), headers=auth)

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), matricula="1234-abc"), headers=auth)

    assert respuesta.status_code == 409
    assert "1234ABC" in respuesta.json()["detail"]


def test_la_matricula_de_un_vehiculo_dado_de_baja_sigue_ocupada(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    """La baja es lógica: el vehículo sigue existiendo (con su historial) y su matrícula también."""
    db, empresa, auth = entorno
    creado = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=auth).json()
    api.delete(f"/vehiculos/{creado['id']}", headers=auth)

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=auth)

    assert respuesta.status_code == 409
    assert "dado de baja" in respuesta.json()["detail"]


def test_la_misma_matricula_en_otra_empresa_se_permite(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    otra = crear_empresa(db, "Otra empresa")
    crear_vehiculo(db, otra, "1234ABC")

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), matricula="1234ABC"), headers=auth)

    assert respuesta.status_code == 201


def test_el_vehiculo_se_crea_siempre_en_la_empresa_del_usuario(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    """GEN-01: enviar empresa_id (para colarlo en otra empresa) se rechaza."""
    db, empresa, auth = entorno
    otra = crear_empresa(db, "Otra empresa")

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), empresa_id=otra.id), headers=auth)

    assert respuesta.status_code == 422


def test_no_se_puede_usar_un_centro_de_otra_empresa(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    centro_ajeno = crear_centro(db, crear_empresa(db, "Otra empresa"))

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), centro_id=centro_ajeno.id), headers=auth)

    assert respuesta.status_code == 422
    assert "centro" in respuesta.json()["detail"]


def test_no_se_puede_usar_un_tipo_que_no_existe(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), tipo_id=999_999), headers=auth)

    assert respuesta.status_code == 422
    assert "tipo" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "campo_invalido",
    [
        {"matricula": "!!"},  # caracteres no permitidos
        {"matricula": "A"},  # demasiado corta
        {"anio": 1800},  # año fuera de rango
        {"capacidad": 0},  # capacidad no positiva
        {"combustible": "carbon"},  # combustible que no existe
        {"marca": "   "},  # solo espacios
        {"km_actuales": -5},  # km negativos
        {"estado": "en_taller"},  # el estado no se elige al dar de alta
    ],
)
def test_datos_invalidos_responden_422(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]], campo_invalido: dict[str, Any]
) -> None:
    db, empresa, auth = entorno

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa), **campo_invalido), headers=auth)

    assert respuesta.status_code == 422


@pytest.mark.parametrize("rol", [RolUsuario.TALLER, RolUsuario.CONDUCTOR])
def test_taller_y_conductor_no_pueden_dar_de_alta(api: TestClient, db: Session, rol: RolUsuario) -> None:
    empresa = crear_empresa(db)
    usuario = crear_usuario(db, empresa, f"{rol}@example.com", rol)

    respuesta = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=cabeceras(usuario))

    assert respuesta.status_code == 403


# --- Consulta ----------------------------------------------------------------


def test_consultar_un_vehiculo_de_otra_empresa_responde_404(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, _, auth = entorno
    ajeno = crear_vehiculo(db, crear_empresa(db, "Otra empresa"))

    assert api.get(f"/vehiculos/{ajeno.id}", headers=auth).status_code == 404


def test_un_vehiculo_dado_de_baja_se_puede_consultar(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    """Su ficha (y en el futuro su historial) sigue accesible tras la baja."""
    db, empresa, auth = entorno
    vehiculo = crear_vehiculo(db, empresa)
    api.delete(f"/vehiculos/{vehiculo.id}", headers=auth)

    respuesta = api.get(f"/vehiculos/{vehiculo.id}", headers=auth)

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert respuesta.json()["estado"] == "baja"


def test_listado_con_filtros(api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]) -> None:
    db, empresa, auth = entorno
    activo = crear_vehiculo(db, empresa, "1111AAA")
    baja = crear_vehiculo(db, empresa, "2222BBB")
    api.delete(f"/vehiculos/{baja.id}", headers=auth)

    def matriculas(params: dict[str, Any]) -> list[str]:
        return [v["matricula"] for v in api.get("/vehiculos", params=params, headers=auth).json()]

    assert matriculas({}) == ["1111AAA"]
    assert matriculas({"incluir_bajas": True}) == ["1111AAA", "2222BBB"]
    assert matriculas({"centro_id": activo.centro_id}) == ["1111AAA"]
    assert matriculas({"tipo_id": activo.tipo_id, "incluir_bajas": True}) == ["1111AAA"]


# --- Edición -----------------------------------------------------------------


def test_editar_solo_cambia_los_campos_enviados(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    creado = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=auth).json()

    respuesta = api.patch(f"/vehiculos/{creado['id']}", json={"marca": "Otra Marca"}, headers=auth)

    assert respuesta.status_code == 200
    assert respuesta.json() == {**creado, "marca": "Otra Marca"}


def test_editar_con_la_misma_matricula_no_es_un_duplicado(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    creado = api.post("/vehiculos", json=datos_alta((db, empresa)), headers=auth).json()

    respuesta = api.patch(f"/vehiculos/{creado['id']}", json={"matricula": "1234 abc"}, headers=auth)

    assert respuesta.status_code == 200


def test_editar_a_una_matricula_ocupada_responde_409(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    crear_vehiculo(db, empresa, "1111AAA")
    segundo = crear_vehiculo(db, empresa, "2222BBB")

    respuesta = api.patch(f"/vehiculos/{segundo.id}", json={"matricula": "1111AAA"}, headers=auth)

    assert respuesta.status_code == 409


def test_vaciar_la_capacidad_se_permite_pero_la_marca_no(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    vehiculo = crear_vehiculo(db, empresa)

    capacidad = api.patch(f"/vehiculos/{vehiculo.id}", json={"capacidad": None}, headers=auth)
    marca = api.patch(f"/vehiculos/{vehiculo.id}", json={"marca": None}, headers=auth)

    assert capacidad.status_code == 200
    assert capacidad.json()["capacidad"] is None
    assert marca.status_code == 422


@pytest.mark.parametrize("campo", [{"estado": "en_taller"}, {"km_actuales": 5000}, {"activo": False}])
def test_estado_km_y_activo_no_se_editan_a_mano(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]], campo: dict[str, Any]
) -> None:
    """El estado lo calcula el motor (FLO-03), los km vienen de lecturas (FLO-05) y la baja va por DELETE."""
    db, empresa, auth = entorno
    vehiculo = crear_vehiculo(db, empresa)

    assert api.patch(f"/vehiculos/{vehiculo.id}", json=campo, headers=auth).status_code == 422


def test_cambiar_a_un_centro_de_otra_empresa_responde_422(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    vehiculo = crear_vehiculo(db, empresa)
    centro_ajeno = crear_centro(db, crear_empresa(db, "Otra empresa"))

    respuesta = api.patch(f"/vehiculos/{vehiculo.id}", json={"centro_id": centro_ajeno.id}, headers=auth)

    assert respuesta.status_code == 422


def test_no_se_edita_un_vehiculo_de_otra_empresa_ni_uno_dado_de_baja(
    api: TestClient, entorno: tuple[Session, Empresa, dict[str, str]]
) -> None:
    db, empresa, auth = entorno
    ajeno = crear_vehiculo(db, crear_empresa(db, "Otra empresa"))
    de_baja = crear_vehiculo(db, empresa)
    api.delete(f"/vehiculos/{de_baja.id}", headers=auth)

    assert api.patch(f"/vehiculos/{ajeno.id}", json={"marca": "X"}, headers=auth).status_code == 404
    assert api.patch(f"/vehiculos/{de_baja.id}", json={"marca": "X"}, headers=auth).status_code == 404


def test_el_taller_no_puede_editar(api: TestClient, db: Session) -> None:
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa)
    taller = crear_usuario(db, empresa, "taller@example.com", RolUsuario.TALLER)

    respuesta = api.patch(f"/vehiculos/{vehiculo.id}", json={"marca": "X"}, headers=cabeceras(taller))

    assert respuesta.status_code == 403
