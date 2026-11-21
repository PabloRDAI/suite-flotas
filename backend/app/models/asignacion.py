"""Asignaciones conductor-vehículo (PER-03).

El historial se conserva: una asignación no se borra al terminar, se le pone
fecha de fin ("hasta"). Sin "hasta", sigue vigente.
"""

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Text, text, true
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa


class Asignacion(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "asignacion"
    __table_args__ = (
        # GEN-01: la persona y el vehículo son de la misma empresa que la asignación.
        ForeignKeyConstraint(
            ["empresa_id", "persona_id"],
            ["persona.empresa_id", "persona.id"],
            name="fk_asignacion_persona_misma_empresa",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_asignacion_vehiculo_misma_empresa",
        ),
        CheckConstraint("hasta IS NULL OR hasta >= desde", name="fechas_en_orden"),
        # PER-03 en la propia BD: dos asignaciones HABITUALES del mismo vehículo no
        # pueden solaparse en el tiempo. daterange(desde, hasta, '[]') es el periodo
        # con los dos días incluidos (hasta NULL = sin fin); && significa "se solapan".
        # Necesita la extensión btree_gist (la activa la migración).
        ExcludeConstraint(
            ("vehiculo_id", "="),
            (text("daterange(desde, hasta, '[]')"), "&&"),
            where=text("habitual"),
            using="gist",
            name="ex_asignacion_un_habitual_a_la_vez",
        ),
        Index("ix_asignacion_vehiculo_id_desde", "vehiculo_id", "desde"),
        Index("ix_asignacion_persona_id_desde", "persona_id", "desde"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int]
    vehiculo_id: Mapped[int]
    desde: Mapped[date]
    hasta: Mapped[date | None]
    # Habitual: su conductor/a de siempre (máx. uno a la vez). Temporal: sustitución o refuerzo.
    habitual: Mapped[bool] = mapped_column(default=True, server_default=true())
    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    def __repr__(self) -> str:
        return f"<Asignacion persona={self.persona_id} vehiculo={self.vehiculo_id} {self.desde}..{self.hasta}>"
