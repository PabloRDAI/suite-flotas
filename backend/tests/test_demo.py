"""Tests de la empresa de demostración (GEN-04)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Centro, Empresa, LecturaKm, RolUsuario, Usuario, Vehiculo
from app.reglas.km import Lectura, comprobar_lectura
from app.servicios.demo import (
    PASSWORD_DEMO,
    DemoYaExiste,
    crear_empresa_demo,
    email_demo,
    planificar_demo,
)
from tests.fabricas import crear_empresa, crear_usuario

HOY = date(2026, 11, 21)


def contar(db: Session, modelo: type, empresa_id: int) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(modelo.empresa_id == empresa_id)) or 0


# --- El plan (Python puro, sin BD) -------------------------------------------


def test_el_plan_es_siempre_el_mismo() -> None:
    """Semilla fija: dos ejecuciones generan exactamente los mismos datos."""
    assert planificar_demo(HOY) == planificar_demo(HOY)


def test_otra_semilla_da_otros_datos() -> None:
    assert planificar_demo(HOY, semilla=1) != planificar_demo(HOY, semilla=2)


def test_el_plan_tiene_25_vehiculos_con_matricula_unica() -> None:
    plan = planificar_demo(HOY)

    assert len(plan) == 25
    assert len({v.matricula for v in plan}) == 25


def test_las_lecturas_cumplen_la_regla_de_km() -> None:
    """Los datos demo respetan FLO-05: cada lectura pasaría la validación de la API."""
    for v in planificar_demo(HOY):
        anteriores: list[Lectura] = []
        for fecha, km in v.lecturas:
            nueva = Lectura(fecha, km)
            comprobar_lectura(nueva, anteriores, HOY)  # lanza excepción si no vale
            anteriores.append(nueva)
        assert v.lecturas[0][0] < v.lecturas[-1][0] <= HOY
        assert (v.lecturas[-1][0] - v.lecturas[0][0]).days >= 175  # ~6 meses de historial


# --- Guardado en la BD -------------------------------------------------------


def test_crea_lo_que_pide_la_spec(db: Session) -> None:
    """GEN-04 (parte disponible hoy): 1 empresa, 2 centros y 25 vehículos con historial."""
    r = crear_empresa_demo(db, hoy=HOY)

    assert db.get(Empresa, r.empresa_id) is not None
    assert contar(db, Centro, r.empresa_id) == 2
    assert contar(db, Vehiculo, r.empresa_id) == 25
    assert contar(db, LecturaKm, r.empresa_id) == r.lecturas_km > 25 * 20
    assert r.vehiculos == 25


def test_un_usuario_de_cada_rol(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    roles = set(db.scalars(select(Usuario.rol).where(Usuario.empresa_id == r.empresa_id)))

    assert roles == set(RolUsuario)


def test_km_actuales_son_los_de_la_ultima_lectura(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    for vehiculo in db.scalars(select(Vehiculo).where(Vehiculo.empresa_id == r.empresa_id)):
        ultima = db.scalar(select(func.max(LecturaKm.km)).where(LecturaKm.vehiculo_id == vehiculo.id))
        assert vehiculo.km_actuales == ultima


def test_hay_casos_para_enseñar_en_el_panel(db: Session) -> None:
    """2 vehículos no aptos (ITV y seguro caducados) y 3 con documentos en ámbar."""
    r = crear_empresa_demo(db, hoy=HOY)

    assert len(r.no_aptos) == 2
    assert len(r.en_ambar) == 3


def test_los_no_aptos_coinciden_con_la_api(api: TestClient, db: Session) -> None:
    """El resumen del script y el endpoint /aptitud aplican las mismas reglas."""
    r = crear_empresa_demo(db, hoy=date.today())
    login = api.post("/auth/login", json={"email": email_demo("trafico"), "password": PASSWORD_DEMO})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    no_aptos = [
        v["matricula"]
        for v in api.get("/vehiculos", headers=auth).json()
        if not api.get(f"/vehiculos/{v['id']}/aptitud", headers=auth).json()["apto"]
    ]

    assert sorted(no_aptos) == sorted(r.no_aptos)


def test_se_puede_hacer_login_con_los_usuarios_demo(api: TestClient, db: Session) -> None:
    crear_empresa_demo(db, hoy=HOY)

    for alias in ("admin", "trafico", "taller", "conductor"):
        respuesta = api.post("/auth/login", json={"email": email_demo(alias), "password": PASSWORD_DEMO})
        assert respuesta.status_code == 200, alias


# --- Repetir la ejecución ----------------------------------------------------


def test_sin_reiniciar_no_se_duplica(db: Session) -> None:
    crear_empresa_demo(db, hoy=HOY)

    with pytest.raises(DemoYaExiste):
        crear_empresa_demo(db, hoy=HOY)


def test_reiniciar_recrea_la_demo_sin_tocar_otras_empresas(db: Session) -> None:
    otra = crear_empresa(db, "Empresa real que no se debe tocar")
    crear_usuario(db, otra, "gerente@example.com")
    primera = crear_empresa_demo(db, hoy=HOY)

    segunda = crear_empresa_demo(db, hoy=HOY, reiniciar=True)

    assert segunda.empresa_id != primera.empresa_id
    assert db.get(Empresa, primera.empresa_id) is None  # la demo anterior se borró entera
    assert db.get(Empresa, otra.id) is not None  # la otra empresa sigue intacta
    assert contar(db, Usuario, otra.id) == 1
    assert db.scalar(select(func.count()).select_from(Empresa).where(Empresa.nombre.like("%Demo%"))) == 1
