"""Piezas compartidas por todos los tests (pytest carga este archivo solo).

Una "fixture" es algo que el test necesita preparado: el test la pide poniendo
su nombre como parámetro y pytest se la entrega.

BASE DE DATOS DE TESTS: los tests NUNCA usan la base de datos de desarrollo.
Antes de cargar la aplicación, este archivo cambia DATABASE_URL a una base de
datos aparte (la misma con el sufijo "_test", o TEST_DATABASE_URL si existe),
la crea si no existe y le aplica las migraciones.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, make_url, text

from app.config import Settings, get_settings

# --- 1. Elegir la base de datos de tests (ANTES de importar app.db) ----------
_url_desarrollo = make_url(Settings().database_url)  # type: ignore[call-arg]
_url_tests = make_url(
    os.environ.get("TEST_DATABASE_URL") or _url_desarrollo.set(database=f"{_url_desarrollo.database}_test")
)
if _url_tests.database == _url_desarrollo.database:
    raise RuntimeError("La base de datos de tests no puede ser la de desarrollo")

os.environ["DATABASE_URL"] = _url_tests.render_as_string(hide_password=False)
get_settings.cache_clear()  # para que la aplicación lea la nueva DATABASE_URL


def _preparar_bd_de_tests() -> None:
    """Crea la base de datos de tests si no existe y le aplica las migraciones."""
    # CREATE DATABASE no puede ejecutarse dentro de una transacción: AUTOCOMMIT.
    servidor = create_engine(_url_tests.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with servidor.connect() as conexion:
        existe = conexion.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :nombre"), {"nombre": _url_tests.database}
        )
        if not existe:
            conexion.execute(text(f'CREATE DATABASE "{_url_tests.database}"'))
    servidor.dispose()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


_preparar_bd_de_tests()

# --- 2. Ahora sí, cargar la aplicación (ya apunta a la BD de tests) -----------
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


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
