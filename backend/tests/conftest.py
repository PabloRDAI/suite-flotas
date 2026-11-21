"""Piezas compartidas por todos los tests (pytest carga este archivo solo).

Una "fixture" es algo que el test necesita preparado: el test la pide poniendo
su nombre como parámetro y pytest se la entrega.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Cliente HTTP de pruebas: hace peticiones a la API sin arrancar un servidor real."""
    with TestClient(app) as c:
        yield c
    # Al terminar cada test se limpian las sustituciones de dependencias,
    # para que un test no afecte a los siguientes.
    app.dependency_overrides.clear()
