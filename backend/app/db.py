"""Conexión a la base de datos con SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

# El "engine" gestiona un conjunto (pool) de conexiones abiertas con PostgreSQL.
# - pool_pre_ping: comprueba que la conexión sigue viva antes de usarla
#   (útil si la base de datos se ha reiniciado).
# - connect_timeout: si PostgreSQL no contesta en N segundos, se da por caído en
#   vez de esperar indefinidamente (en Windows + Docker, una BD parada no
#   rechaza la conexión: simplemente no responde).
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": _settings.db_connect_timeout},
)

# Fábrica de sesiones: cada petición HTTP abrirá su propia sesión.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Convención de nombres para índices y restricciones. Así cada restricción tiene
# un nombre predecible (p. ej. "uq_vehiculo_empresa_id_matricula") y Alembic
# puede modificarla o borrarla sin problemas en migraciones futuras.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos (tablas)."""

    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión para la petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
