"""Centro o base de la empresa: cocheras, talleres, oficinas (GEN-03)."""

from enum import StrEnum

from sqlalchemy import String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto


class TipoCentro(StrEnum):
    COCHERA = "cochera"
    TALLER = "taller"
    OFICINA = "oficina"
    OTRO = "otro"


class Centro(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "centro"
    __table_args__ = (
        # Dos centros de la misma empresa no pueden llamarse igual.
        UniqueConstraint("empresa_id", "nombre"),
        # Necesaria para que otras tablas puedan exigir "centro de MI empresa"
        # con una clave foránea compuesta (empresa_id, centro_id). Ver Vehiculo.
        UniqueConstraint("empresa_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[TipoCentro] = mapped_column(enum_texto(TipoCentro, "tipo_centro"), default=TipoCentro.COCHERA)
    direccion: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<Centro {self.id} {self.nombre!r}>"
