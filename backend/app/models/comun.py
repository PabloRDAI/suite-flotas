"""Piezas reutilizables por varios modelos (mixins y tipos)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class ConMarcasDeTiempo:
    """Mixin: añade cuándo se creó y cuándo se modificó por última vez cada fila.

    Las fechas las pone PostgreSQL (server_default=now()), no el código, para
    que sean coherentes aunque se inserten datos desde otro sitio.
    """

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DeEmpresa:
    """Mixin: liga la fila a una empresa (requisito GEN-01, multiempresa).

    Todas las tablas con datos de negocio heredan de aquí, de modo que siempre
    se puede filtrar "solo lo de mi empresa". El índice acelera ese filtro.
    """

    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id", ondelete="RESTRICT"), index=True)


def enum_texto[E: StrEnum](enum_cls: type[E], nombre: str) -> Enum:
    """Columna que guarda un StrEnum como texto, con un CHECK en la BD.

    - Se guarda el valor ("en_taller"), no el nombre Python ("EN_TALLER").
    - native_enum=False: VARCHAR + CHECK en vez de un tipo ENUM de PostgreSQL,
      que es más fácil de ampliar en migraciones (añadir un valor nuevo).
    - create_constraint=True: la BD rechaza cualquier valor fuera de la lista.
    """
    return Enum(
        enum_cls,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
