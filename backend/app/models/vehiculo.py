"""Tipos de vehículo (FLO-02) y vehículos (FLO-01)."""

from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto

# El estado se define en el motor de reglas (Python puro), que es quien lo calcula.
from app.reglas.estado_vehiculo import EstadoVehiculo

__all__ = ["Combustible", "EstadoVehiculo", "TipoVehiculo", "UnidadCapacidad", "Vehiculo"]


class UnidadCapacidad(StrEnum):
    PLAZAS = "plazas"  # viajeros (autobús, microbús)
    KG = "kg"  # mercancías (furgoneta, camión, cisterna)


class TipoVehiculo(DeEmpresa, ConMarcasDeTiempo, Base):
    """Tipo configurable por cada empresa (autobús, camión, cisterna…), no fijo en el código."""

    __tablename__ = "tipo_vehiculo"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nombre"),
        UniqueConstraint("empresa_id", "id"),  # para la FK compuesta desde vehiculo
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    # Indica cómo se interpreta Vehiculo.capacidad para este tipo.
    unidad_capacidad: Mapped[UnidadCapacidad] = mapped_column(
        enum_texto(UnidadCapacidad, "unidad_capacidad"), default=UnidadCapacidad.PLAZAS
    )
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<TipoVehiculo {self.id} {self.nombre!r}>"


class Combustible(StrEnum):
    DIESEL = "diesel"
    GASOLINA = "gasolina"
    ELECTRICO = "electrico"
    HIBRIDO = "hibrido"
    GNC = "gnc"  # gas natural comprimido
    GNL = "gnl"  # gas natural licuado
    GLP = "glp"  # gas licuado del petróleo
    HIDROGENO = "hidrogeno"
    OTRO = "otro"


class Vehiculo(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "vehiculo"
    __table_args__ = (
        # FLO-01: la matrícula es única dentro de la empresa
        # (otra empresa sí puede tener la misma matrícula en su sistema).
        UniqueConstraint("empresa_id", "matricula"),
        # Para las FK compuestas desde otras tablas (lecturas de km, averías…).
        UniqueConstraint("empresa_id", "id"),
        # GEN-01 reforzado en la BD: el centro y el tipo deben ser de la MISMA
        # empresa que el vehículo. Con una FK simple (centro_id -> centro.id)
        # se podría asignar por error un centro de otra empresa.
        ForeignKeyConstraint(
            ["empresa_id", "centro_id"],
            ["centro.empresa_id", "centro.id"],
            name="fk_vehiculo_centro_misma_empresa",
        ),
        ForeignKeyConstraint(
            ["empresa_id", "tipo_id"],
            ["tipo_vehiculo.empresa_id", "tipo_vehiculo.id"],
            name="fk_vehiculo_tipo_misma_empresa",
        ),
        CheckConstraint("km_actuales >= 0", name="km_no_negativos"),
        CheckConstraint("anio BETWEEN 1950 AND 2100", name="anio_razonable"),
        CheckConstraint("capacidad IS NULL OR capacidad > 0", name="capacidad_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    centro_id: Mapped[int] = mapped_column(index=True)
    tipo_id: Mapped[int] = mapped_column(index=True)
    matricula: Mapped[str] = mapped_column(String(15))
    marca: Mapped[str] = mapped_column(String(50))
    modelo: Mapped[str] = mapped_column(String(80))
    anio: Mapped[int]
    # Plazas o kg según TipoVehiculo.unidad_capacidad.
    capacidad: Mapped[int | None]
    combustible: Mapped[Combustible] = mapped_column(enum_texto(Combustible, "combustible"))
    # FLO-05: pasará a ser el valor de la última lectura de km.
    km_actuales: Mapped[int] = mapped_column(default=0, server_default="0")
    # FLO-03: nunca se asigna a mano; lo calcula app/servicios/estado_vehiculo.py (regla 1).
    estado: Mapped[EstadoVehiculo] = mapped_column(
        enum_texto(EstadoVehiculo, "estado_vehiculo"), default=EstadoVehiculo.OPERATIVO
    )
    # Baja lógica (FLO-01): no se borra la fila, se marca como inactiva y se conserva el historial.
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<Vehiculo {self.id} {self.matricula!r}>"
