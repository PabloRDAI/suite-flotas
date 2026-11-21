"""Piezas compartidas por todos los tests (pytest carga este archivo solo).

Una "fixture" es algo que el test necesita preparado: el test la pide poniendo
su nombre como parámetro y pytest se la entrega.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Cliente HTTP de pruebas: hace peticiones a la API sin arrancar un servidor real."""
    with TestClient(app) as c:
        yield c
    # Al terminar cada test se limpian las sustituciones de dependencias,
    # para que un test no afecte a los siguientes.
    app.dependency_overrides.clear()


@pytest.fixture
def db() -> Iterator[Session]:
    """Sesión de base de datos cuyos cambios se DESHACEN al acabar el test.

    Requiere PostgreSQL en marcha y las migraciones aplicadas (alembic upgrade head).

    Cómo funciona:
    1. Abrimos una conexión y empezamos una transacción "exterior".
    2. La sesión trabaja dentro de ella usando savepoints (puntos de guardado):
       si un test provoca un error de la BD, solo se deshace hasta el savepoint.
    3. Al terminar, deshacemos la transacción exterior: la BD queda como estaba.
    """
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    """Cliente HTTP cuyos endpoints usan la MISMA sesión que el test (fixture `db`).

    Así los datos que crea el test son visibles para la API, y lo que haga la
    API (incluidos sus commits, que aquí son savepoints) se deshace al final.
    """
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
