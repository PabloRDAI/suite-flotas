"""Tipos de vencimiento y vencimientos de documentación de vehículos (FLO-06) y personas (PER-02)."""

from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto


class AplicaA(StrEnum):
    VEHICULO = "vehiculo"  # ITV, seguro, tacógrafo, tarjeta de transporte…
    PERSONA = "persona"  # permiso de conducir, CAP, tarjeta de conductor… (PER-02)


class TipoVencimiento(DeEmpresa, ConMarcasDeTiempo, Base):
    """Tipo de documento que caduca, configurado por cada empresa.

    Los plazos legales NO se escriben en el código (requisito de la spec): cada
    empresa crea sus tipos y decide con cuántos días de antelación avisar.
    """

    __tablename__ = "tipo_vencimiento"
    __table_args__ = (
        UniqueConstraint("empresa_id", "aplica_a", "nombre"),
        UniqueConstraint("empresa_id", "id"),  # para la FK compuesta desde vencimiento
        CheckConstraint("dias_aviso BETWEEN 0 AND 365", name="dias_aviso_razonables"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    aplica_a: Mapped[AplicaA] = mapped_column(enum_texto(AplicaA, "aplica_a"), default=AplicaA.VEHICULO)
    # Días antes de la caducidad en que el semáforo pasa a ámbar (FLO-06).
    dias_aviso: Mapped[int] = mapped_column(default=30, server_default="30")
    # Si está caducado, ¿impide que el vehículo salga? (FLO-07)
    bloquea_salida: Mapped[bool] = mapped_column(default=True, server_default=true())
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<TipoVencimiento {self.id} {self.nombre!r} ({self.aplica_a})>"


class Vencimiento(DeEmpresa, ConMarcasDeTiempo, Base):
    """Un documento concreto con su fecha de caducidad.

    Al renovar un documento se crea un vencimiento nuevo y el anterior queda
    como historial: de cada tipo cuenta el que caduca más tarde (app/reglas/vencimientos.py).
    """

    __tablename__ = "vencimiento"
    __table_args__ = (
        # Cada vencimiento es de un vehículo (FLO-06) O de una persona (PER-02): exactamente uno.
        CheckConstraint("num_nonnulls(vehiculo_id, persona_id) = 1", name="un_solo_titular"),
        # GEN-01: el tipo, el vehículo y la persona son de la misma empresa que el vencimiento.
        ForeignKeyConstraint(
            ["empresa_id", "tipo_id"],
            ["tipo_vencimiento.empresa_id", "tipo_vencimiento.id"],
            name="fk_vencimiento_tipo_misma_empresa",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "vehiculo_id"],
            ["vehiculo.empresa_id", "vehiculo.id"],
            name="fk_vencimiento_vehiculo_misma_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "persona_id"],
            ["persona.empresa_id", "persona.id"],
            name="fk_vencimiento_persona_misma_empresa",
            ondelete="CASCADE",
        ),
        Index("ix_vencimiento_vehiculo_id_tipo_id", "vehiculo_id", "tipo_id"),
        Index("ix_vencimiento_persona_id_tipo_id", "persona_id", "tipo_id"),
        # Para buscar rápido "lo que caduca pronto" en toda la empresa (panel, FLO-04).
        Index("ix_vencimiento_empresa_id_fecha_caducidad", "empresa_id", "fecha_caducidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_id: Mapped[int]
    # Titular: uno de los dos (lo garantiza el CHECK "un_solo_titular").
    vehiculo_id: Mapped[int | None]
    persona_id: Mapped[int | None]
    fecha_caducidad: Mapped[date]
    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    def __repr__(self) -> str:
        return f"<Vencimiento {self.id} tipo={self.tipo_id} caduca={self.fecha_caducidad}>"
