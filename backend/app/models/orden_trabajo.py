"""Órdenes de trabajo (MAN-04, MAN-05) y sus líneas de coste (MAN-06)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto
from app.reglas.estado_vehiculo import EstadoOT
from app.reglas.ordenes import Concepto, OrigenOT, TipoOT


class OrdenTrabajo(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "orden_trabajo"
    __table_args__ = (
        UniqueConstraint("empresa_id", "id"),  # para la FK compuesta desde las líneas
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_orden_trabajo_vehiculo_misma_empresa",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "plan_id"],
            ["plan_mantenimiento.empresa_id", "plan_mantenimiento.id"],
            name="fk_orden_trabajo_plan_misma_empresa",
        ),
        # MAN-05: "al cerrar se exigen los km y la fecha", también en la BD.
        CheckConstraint(
            "estado <> 'cerrada' OR (fecha_cierre IS NOT NULL AND km_cierre IS NOT NULL)",
            name="cerrada_con_fecha_y_km",
        ),
        # El origen y su enlace van juntos.
        CheckConstraint(
            "(origen <> 'plan' OR plan_id IS NOT NULL) AND (origen <> 'averia' OR averia_id IS NOT NULL)",
            name="origen_enlazado",
        ),
        CheckConstraint("km_cierre IS NULL OR km_cierre >= 0", name="km_no_negativos"),
        # Consultas habituales: OT abiertas de un vehículo (estado del vehículo, tablero de taller).
        Index("ix_orden_trabajo_vehiculo_id_estado", "vehiculo_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int]
    tipo: Mapped[TipoOT] = mapped_column(enum_texto(TipoOT, "tipo_ot"))
    origen: Mapped[OrigenOT] = mapped_column(enum_texto(OrigenOT, "origen_ot"))
    estado: Mapped[EstadoOT] = mapped_column(enum_texto(EstadoOT, "estado_ot"), default=EstadoOT.ABIERTA)
    plan_id: Mapped[int | None]
    averia_id: Mapped[int | None] = mapped_column(ForeignKey("averia.id"), index=True)
    # Si inmoviliza, mientras esté abierta o en curso el vehículo está "en taller" (regla 1).
    inmoviliza: Mapped[bool]
    descripcion: Mapped[str] = mapped_column(Text)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("persona.id", ondelete="SET NULL"))
    creada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    abierta_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    iniciada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Cierre (MAN-05): fecha y km obligatorios; los km se registran también como lectura.
    fecha_cierre: Mapped[date | None]
    km_cierre: Mapped[int | None]
    trabajo_realizado: Mapped[str | None] = mapped_column(Text)
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<OrdenTrabajo {self.id} {self.tipo} {self.estado} vehiculo={self.vehiculo_id}>"


class LineaOT(DeEmpresa, Base):
    """Una línea de coste: mano de obra (horas × tarifa), recambio (unidades × precio) o externo."""

    __tablename__ = "linea_ot"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empresa_id", "ot_id"],
            ["orden_trabajo.empresa_id", "orden_trabajo.id"],
            name="fk_linea_ot_ot_misma_empresa",
            ondelete="CASCADE",
        ),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="precio_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ot_id: Mapped[int] = mapped_column(index=True)
    concepto: Mapped[Concepto] = mapped_column(enum_texto(Concepto, "concepto_linea"))
    descripcion: Mapped[str] = mapped_column(String(200))
    # Numeric (decimal exacto) y no float: es dinero.
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
