"""Averías comunicadas (MAN-03).

La gravedad "inmoviliza" deja el vehículo inmovilizado (regla 1, FLO-03) hasta
que la avería se resuelve o pasa a una orden de trabajo (MAN-04).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto
from app.reglas.estado_vehiculo import EstadoAveria, GravedadAveria


class Averia(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "averia"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_averia_vehiculo_misma_empresa",
        ),
        # Consulta habitual: averías abiertas de un vehículo (estado del vehículo, ficha).
        Index("ix_averia_vehiculo_id_estado", "vehiculo_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int]
    comunicada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    comunicada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    descripcion: Mapped[str] = mapped_column(Text)
    gravedad: Mapped[GravedadAveria] = mapped_column(enum_texto(GravedadAveria, "gravedad_averia"))
    estado: Mapped[EstadoAveria] = mapped_column(
        enum_texto(EstadoAveria, "estado_averia"), default=EstadoAveria.COMUNICADA
    )
    # Nombre del archivo en la carpeta de adjuntos (aleatorio, nunca el original del usuario).
    foto: Mapped[str | None] = mapped_column(String(100))
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nota_resolucion: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Averia {self.id} vehiculo={self.vehiculo_id} {self.gravedad} {self.estado}>"
