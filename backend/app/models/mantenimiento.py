"""Planes de mantenimiento preventivo (MAN-01).

- PlanMantenimiento: por tipo de vehículo, "cada X km o Y días (lo que llegue antes)".
- TareaPlan: lo que hay que hacer en cada mantenimiento del plan.
- EstadoPlan: para cada vehículo y plan, cuándo se hizo el último y cuándo toca el próximo.
"""

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa


class PlanMantenimiento(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "plan_mantenimiento"
    __table_args__ = (
        UniqueConstraint("empresa_id", "tipo_vehiculo_id", "nombre"),
        UniqueConstraint("empresa_id", "id"),  # para FK compuestas (tareas, estados)
        ForeignKeyConstraint(
            ["empresa_id", "tipo_vehiculo_id"],
            ["tipo_vehiculo.empresa_id", "tipo_vehiculo.id"],
            name="fk_plan_mantenimiento_tipo_misma_empresa",
        ),
        # Al menos un intervalo, y los que haya, positivos.
        CheckConstraint(
            "(intervalo_km IS NOT NULL OR intervalo_dias IS NOT NULL)"
            " AND (intervalo_km IS NULL OR intervalo_km > 0)"
            " AND (intervalo_dias IS NULL OR intervalo_dias > 0)",
            name="intervalos_validos",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_vehiculo_id: Mapped[int] = mapped_column(index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    intervalo_km: Mapped[int | None]
    intervalo_dias: Mapped[int | None]
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<PlanMantenimiento {self.id} {self.nombre!r} km={self.intervalo_km} días={self.intervalo_dias}>"


class TareaPlan(DeEmpresa, Base):
    __tablename__ = "tarea_plan"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empresa_id", "plan_id"],
            ["plan_mantenimiento.empresa_id", "plan_mantenimiento.id"],
            name="fk_tarea_plan_plan_misma_empresa",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(index=True)
    orden: Mapped[int]  # posición en la lista (1, 2, 3…)
    descripcion: Mapped[str] = mapped_column(String(200))


class EstadoPlan(DeEmpresa, ConMarcasDeTiempo, Base):
    """Situación de un plan en un vehículo. Las "próximas" se guardan ya calculadas
    con la regla 3 (app/reglas/preventivo.py) para poder consultarlas rápido."""

    __tablename__ = "estado_plan"
    __table_args__ = (
        UniqueConstraint("vehiculo_id", "plan_id"),
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_estado_plan_vehiculo_misma_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "plan_id"],
            ["plan_mantenimiento.empresa_id", "plan_mantenimiento.id"],
            name="fk_estado_plan_plan_misma_empresa",
            ondelete="CASCADE",
        ),
        CheckConstraint("ultimos_km >= 0", name="km_no_negativos"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int]
    plan_id: Mapped[int] = mapped_column(index=True)
    ultima_fecha: Mapped[date]
    ultimos_km: Mapped[int]
    proxima_fecha: Mapped[date | None]
    proximos_km: Mapped[int | None]
