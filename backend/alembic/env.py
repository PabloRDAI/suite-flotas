"""Entorno de Alembic: cómo se conecta a la BD y qué modelos compara.

Alembic ejecuta este archivo en cada comando (upgrade, downgrade, revision...).
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.db import Base

# Objeto de configuración de Alembic (lee alembic.ini).
config = context.config

# La URL de la base de datos sale del .env, igual que en la aplicación:
# una única fuente de verdad, sin contraseñas en alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Configura los logs según alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadatos de nuestros modelos. Con esto, "alembic revision --autogenerate"
# compara las clases Python con las tablas reales y genera la migración.
# IMPORTANTE: importar aquí los módulos de modelos para que
# se registren en Base.metadata, p. ej.:  import app.models  # noqa: F401
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo 'offline': genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo normal: se conecta a la base de datos y aplica las migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detecta también cambios de tipo de columna
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
