"""Conexión a la base de datos con SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# El "engine" gestiona un conjunto (pool) de conexiones abiertas con PostgreSQL.
# pool_pre_ping comprueba que la conexión sigue viva antes de usarla
# (útil si la base de datos se ha reiniciado).
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# Fábrica de sesiones: cada petición HTTP abrirá su propia sesión.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredarán todos los modelos (tablas)."""


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión para la petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
