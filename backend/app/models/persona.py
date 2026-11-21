"""Personal de la empresa (PER-01).

Privacidad (RGPD, spec): datos mínimos. Sin DNI ni datos bancarios en el MVP;
la tabla simplemente no tiene esas columnas.
"""

from datetime import date
from enum import StrEnum

from sqlalchemy import ForeignKeyConstraint, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto


class Puesto(StrEnum):
    CONDUCTOR = "conductor"
    MECANICO = "mecanico"
    TRAFICO = "trafico"
    OTRO = "otro"


class Persona(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "persona"
    __table_args__ = (
        UniqueConstraint("empresa_id", "id"),  # para FK compuestas (vencimientos, asignaciones)
        # Una persona como mucho por usuario de la aplicación.
        UniqueConstraint("usuario_id"),
        # GEN-01: el centro y el usuario enlazado son de la misma empresa.
        ForeignKeyConstraint(
            ["empresa_id", "centro_id"],
            ["centro.empresa_id", "centro.id"],
            name="fk_persona_centro_misma_empresa",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "usuario_id"],
            ["usuario.empresa_id", "usuario.id"],
            name="fk_persona_usuario_misma_empresa",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    puesto: Mapped[Puesto] = mapped_column(enum_texto(Puesto, "puesto"))
    centro_id: Mapped[int] = mapped_column(index=True)
    fecha_alta: Mapped[date]
    # Baja lógica: no se borra (se conservan su historial y sus asignaciones).
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    fecha_baja: Mapped[date | None]
    # Usuario de la aplicación de esta persona, si lo tiene (p. ej. un conductor que comunica averías).
    usuario_id: Mapped[int | None]

    def __repr__(self) -> str:
        return f"<Persona {self.id} {self.nombre!r} ({self.puesto})>"
