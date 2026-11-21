"""Tests del endpoint /salud."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_salud_ok_con_base_de_datos(client: TestClient) -> None:
    """Con PostgreSQL en marcha, /salud responde 200 y confirma la conexión.

    Este test usa la base de datos REAL (docker compose up -d).
    """
    respuesta = client.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_de_datos": "ok"}


def test_salud_503_si_la_base_de_datos_falla(client: TestClient) -> None:
    """Si la base de datos no responde, /salud devuelve 503 en vez de romperse.

    Sustituimos la sesión real por una falsa (mock) que lanza un error al
    ejecutar la consulta, simulando que PostgreSQL está caído.
    """
    sesion_rota = MagicMock()
    sesion_rota.execute.side_effect = OperationalError("SELECT 1", {}, Exception("BD caída"))
    app.dependency_overrides[get_db] = lambda: sesion_rota

    respuesta = client.get("/salud")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "error", "base_de_datos": "sin conexión"}
