"""Tests de las lecturas de km por la API (FLO-05).

La regla en sí se prueba a fondo en test_reglas_km.py; aquí se comprueba que la
API la aplica, guarda las lecturas, mantiene km_actuales y respeta los permisos.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import RolUsuario
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, crear_vehiculo

HOY = date.today()
HACE_10_DIAS = HOY - timedelta(days=10)
HACE_5_DIAS = HOY - timedelta(days=5)


@pytest.fixture
def flota(api: TestClient, db: Session) -> dict:
    """Empresa con un admin, un conductor y un vehículo dado de alta con 1.000 km."""
    empresa = crear_empresa(db)
    admin = cabeceras(crear_usuario(db, empresa, "admin@example.com"))
    conductor = cabeceras(crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR))
    vehiculo = api.post(
        "/vehiculos",
        json={
            "matricula": "1234ABC",
            "centro_id": crear_centro(db, empresa).id,
            "tipo_id": crear_tipo(db, empresa).id,
            "marca": "Marca",
            "modelo": "Modelo",
            "anio": 2020,
            "combustible": "diesel",
            "km_actuales": 1000,
        },
        headers=admin,
    ).json()
    return {"empresa": empresa, "admin": admin, "conductor": conductor, "id": vehiculo["id"]}


def km_actuales(api: TestClient, flota: dict) -> int:
    return api.get(f"/vehiculos/{flota['id']}", headers=flota["admin"]).json()["km_actuales"]


def historial(api: TestClient, flota: dict) -> list[tuple[str, int]]:
    lecturas = api.get(f"/vehiculos/{flota['id']}/km", headers=flota["admin"]).json()
    return [(l["fecha"], l["km"]) for l in lecturas]


# --- Lectura inicial ---------------------------------------------------------


def test_el_alta_crea_la_lectura_inicial(api: TestClient, flota: dict) -> None:
    assert historial(api, flota) == [(HOY.isoformat(), 1000)]


# --- Registrar lecturas ------------------------------------------------------


def test_una_lectura_mayor_actualiza_los_km_actuales(api: TestClient, flota: dict) -> None:
    respuesta = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1500}, headers=flota["admin"])

    assert respuesta.status_code == 201
    assert respuesta.json()["fecha"] == HOY.isoformat()  # sin fecha, se usa hoy
    assert km_actuales(api, flota) == 1500


def test_una_lectura_menor_que_la_anterior_se_rechaza(api: TestClient, flota: dict) -> None:
    """Criterio de aceptación literal de FLO-05: no cambia nada."""
    respuesta = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 999}, headers=flota["admin"])

    assert respuesta.status_code == 422
    assert "menores que los de la lectura anterior (1.000 km" in respuesta.json()["detail"]
    assert km_actuales(api, flota) == 1000
    assert len(historial(api, flota)) == 1


def test_una_lectura_atrasada_que_encaja_no_cambia_los_km_actuales(api: TestClient, flota: dict) -> None:
    """Hace 10 días: 800 km. Hoy: 1.000 (el alta). Registrar hace 5 días 900 km es coherente."""
    api.post(f"/vehiculos/{flota['id']}/km", json={"km": 800, "fecha": str(HACE_10_DIAS)}, headers=flota["admin"])

    respuesta = api.post(
        f"/vehiculos/{flota['id']}/km", json={"km": 900, "fecha": str(HACE_5_DIAS)}, headers=flota["admin"]
    )

    assert respuesta.status_code == 201
    assert km_actuales(api, flota) == 1000  # la última sigue siendo la de hoy
    # El historial sale de la más reciente a la más antigua.
    assert historial(api, flota) == [(str(HOY), 1000), (str(HACE_5_DIAS), 900), (str(HACE_10_DIAS), 800)]


def test_una_lectura_atrasada_mayor_que_una_posterior_se_rechaza(api: TestClient, flota: dict) -> None:
    respuesta = api.post(
        f"/vehiculos/{flota['id']}/km", json={"km": 5000, "fecha": str(HACE_5_DIAS)}, headers=flota["admin"]
    )

    assert respuesta.status_code == 422
    assert "posterior" in respuesta.json()["detail"]


def test_una_fecha_futura_se_rechaza(api: TestClient, flota: dict) -> None:
    manana = str(HOY + timedelta(days=1))

    respuesta = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 2000, "fecha": manana}, headers=flota["admin"])

    assert respuesta.status_code == 422


@pytest.mark.parametrize("datos", [{"km": -1}, {"km": 20_000_000}, {"km": "mil"}, {"km": 10, "notas": "x"}])
def test_datos_invalidos_responden_422(api: TestClient, flota: dict, datos: dict) -> None:
    assert api.post(f"/vehiculos/{flota['id']}/km", json=datos, headers=flota["admin"]).status_code == 422


def test_el_conductor_puede_registrar_km(api: TestClient, flota: dict) -> None:
    respuesta = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1200}, headers=flota["conductor"])

    assert respuesta.status_code == 201


def test_no_se_registran_km_en_vehiculos_de_otra_empresa(api: TestClient, db: Session, flota: dict) -> None:
    ajeno = crear_vehiculo(db, crear_empresa(db, "Otra empresa"))

    assert api.post(f"/vehiculos/{ajeno.id}/km", json={"km": 10}, headers=flota["admin"]).status_code == 404
    assert api.get(f"/vehiculos/{ajeno.id}/km", headers=flota["admin"]).status_code == 404


def test_un_vehiculo_dado_de_baja_no_recibe_lecturas_pero_conserva_su_historial(
    api: TestClient, flota: dict
) -> None:
    api.delete(f"/vehiculos/{flota['id']}", headers=flota["admin"])

    assert api.post(f"/vehiculos/{flota['id']}/km", json={"km": 2000}, headers=flota["admin"]).status_code == 404
    assert historial(api, flota) == [(str(HOY), 1000)]


# --- Borrar lecturas erróneas ------------------------------------------------


def test_borrar_una_lectura_erronea_recalcula_los_km(api: TestClient, flota: dict) -> None:
    """Error de tecleo: 1.000.000 en vez de 1.100. Sin poder borrarla, bloquearía todo."""
    erronea = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1_000_000}, headers=flota["admin"]).json()
    assert km_actuales(api, flota) == 1_000_000

    respuesta = api.delete(f"/vehiculos/{flota['id']}/km/{erronea['id']}", headers=flota["admin"])

    assert respuesta.status_code == 204
    assert km_actuales(api, flota) == 1000
    # Y ya se puede registrar la lectura correcta.
    assert api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1100}, headers=flota["admin"]).status_code == 201


def test_no_se_puede_borrar_la_unica_lectura(api: TestClient, flota: dict) -> None:
    (unica,) = api.get(f"/vehiculos/{flota['id']}/km", headers=flota["admin"]).json()

    respuesta = api.delete(f"/vehiculos/{flota['id']}/km/{unica['id']}", headers=flota["admin"])

    assert respuesta.status_code == 409


def test_el_conductor_no_puede_borrar_lecturas(api: TestClient, flota: dict) -> None:
    lectura = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1100}, headers=flota["conductor"]).json()

    respuesta = api.delete(f"/vehiculos/{flota['id']}/km/{lectura['id']}", headers=flota["conductor"])

    assert respuesta.status_code == 403


def test_no_se_borra_una_lectura_a_traves_de_otro_vehiculo(api: TestClient, db: Session, flota: dict) -> None:
    """La lectura debe pertenecer al vehículo de la URL."""
    lectura = api.post(f"/vehiculos/{flota['id']}/km", json={"km": 1100}, headers=flota["admin"]).json()
    otro = crear_vehiculo(db, flota["empresa"], "9999ZZZ")

    respuesta = api.delete(f"/vehiculos/{otro.id}/km/{lectura['id']}", headers=flota["admin"])

    assert respuesta.status_code == 404
