"""Tipos de vehículo configurables por cada empresa (FLO-02)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import Db, SoloAdmin, UsuarioActual
from app.models import TipoVehiculo
from app.schemas import TipoVehiculoCrear, TipoVehiculoSalida

router = APIRouter(prefix="/tipos-vehiculo", tags=["configuración"])


@router.get("")
def listar_tipos(usuario: UsuarioActual, db: Db) -> list[TipoVehiculoSalida]:
    """Tipos activos de la empresa del usuario (para el formulario de alta de vehículo)."""
    tipos = db.scalars(
        select(TipoVehiculo)
        .where(TipoVehiculo.empresa_id == usuario.empresa_id, TipoVehiculo.activo)
        .order_by(TipoVehiculo.nombre)
    )
    return [TipoVehiculoSalida.model_validate(t) for t in tipos]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_tipo(datos: TipoVehiculoCrear, usuario: SoloAdmin, db: Db) -> TipoVehiculoSalida:
    """FLO-02: el admin crea un tipo nuevo y aparece en el formulario de alta. 409 si el nombre ya existe."""
    existe = db.scalar(
        select(TipoVehiculo.id).where(
            TipoVehiculo.empresa_id == usuario.empresa_id, TipoVehiculo.nombre == datos.nombre
        )
    )
    if existe:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un tipo de vehículo llamado '{datos.nombre}'")

    tipo = TipoVehiculo(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(tipo)
    db.commit()
    return TipoVehiculoSalida.model_validate(tipo)
