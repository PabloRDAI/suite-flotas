"""Tests de centros (GEN-03) y tipos de vehículo (FLO-02) por la API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import RolUsuario
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario

# Cada caso: (ruta, JSON válido de alta)
CATALOGOS = [
    ("/centros", {"nombre": "Cochera Norte", "tipo": "cochera", "direccion": "Calle Ficticia 1"}),
    ("/tipos-vehiculo", {"nombre": "Cisterna", "unidad_capacidad": "kg"}),
]


@pytest.mark.parametrize(("ruta", "datos"), CATALOGOS)
def test_el_admin_crea_y_aparece_en_el_listado(api: TestClient, db: Session, ruta: str, datos: dict) -> None:
    """FLO-02: "el admin crea un tipo nuevo y aparece en el formulario de alta"."""
    admin = crear_usuario(db, crear_empresa(db))

    creado = api.post(ruta, json=datos, headers=cabeceras(admin))

    assert creado.status_code == 201
    assert creado.json()["nombre"] == datos["nombre"]
    assert creado.json() in api.get(ruta, headers=cabeceras(admin)).json()


@pytest.mark.parametrize(("ruta", "datos"), CATALOGOS)
def test_nombre_repetido_responde_409(api: TestClient, db: Session, ruta: str, datos: dict) -> None:
    admin = crear_usuario(db, crear_empresa(db))
    api.post(ruta, json=datos, headers=cabeceras(admin))

    assert api.post(ruta, json=datos, headers=cabeceras(admin)).status_code == 409


@pytest.mark.parametrize(("ruta", "datos"), CATALOGOS)
@pytest.mark.parametrize("rol", [RolUsuario.TRAFICO, RolUsuario.TALLER, RolUsuario.CONDUCTOR])
def test_solo_el_admin_configura(api: TestClient, db: Session, ruta: str, datos: dict, rol: RolUsuario) -> None:
    usuario = crear_usuario(db, crear_empresa(db), f"{rol}@example.com", rol)

    assert api.post(ruta, json=datos, headers=cabeceras(usuario)).status_code == 403
    assert api.get(ruta, headers=cabeceras(usuario)).status_code == 200  # pero sí consultan


def test_cada_empresa_solo_ve_sus_centros_y_tipos(api: TestClient, db: Session) -> None:
    empresa_a = crear_empresa(db, "Empresa A")
    empresa_b = crear_empresa(db, "Empresa B")
    crear_centro(db, empresa_a, "Centro de A")
    crear_centro(db, empresa_b, "Centro de B")
    crear_tipo(db, empresa_a, "Tipo de A")
    crear_tipo(db, empresa_b, "Tipo de B")
    usuario_a = crear_usuario(db, empresa_a, "a@example.com", RolUsuario.CONDUCTOR)

    centros = [c["nombre"] for c in api.get("/centros", headers=cabeceras(usuario_a)).json()]
    tipos = [t["nombre"] for t in api.get("/tipos-vehiculo", headers=cabeceras(usuario_a)).json()]

    assert centros == ["Centro de A"]
    assert tipos == ["Tipo de A"]
