"""Lecturas de km de un vehículo (FLO-05)."""

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa


class LecturaKm(DeEmpresa, ConMarcasDeTiempo, Base):
    """Cuántos km marcaba un vehículo en una fecha.

    Vehiculo.km_actuales es siempre el valor de la última lectura (lo mantiene
    la API usando app/reglas/km.py).
    """

    __tablename__ = "lectura_km"
    __table_args__ = (
        # GEN-01: la lectura y su vehículo son de la misma empresa.
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_lectura_km_vehiculo_misma_empresa",
            ondelete="CASCADE",  # si algún día se borra un vehículo de verdad, sus lecturas también
        ),
        CheckConstraint("km >= 0 AND km <= 10000000", name="km_razonables"),
        # Consulta habitual: lecturas de un vehículo ordenadas por fecha.
        Index("ix_lectura_km_vehiculo_id_fecha", "vehiculo_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int]
    fecha: Mapped[date]
    km: Mapped[int]
    # Quién la registró (si se borra el usuario, la lectura se conserva sin autor).
    registrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    def __repr__(self) -> str:
        return f"<LecturaKm vehiculo={self.vehiculo_id} {self.fecha} {self.km} km>"
