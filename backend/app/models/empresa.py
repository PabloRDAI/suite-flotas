"""Empresa: la raíz de todos los datos (multiempresa, GEN-01)."""

from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo


class Empresa(ConMarcasDeTiempo, Base):
    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<Empresa {self.id} {self.nombre!r}>"
