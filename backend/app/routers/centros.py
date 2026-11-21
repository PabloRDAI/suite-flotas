"""Centros o bases de la empresa (GEN-03)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import Db, SoloAdmin, UsuarioActual
from app.models import Centro
from app.schemas import CentroCrear, CentroSalida

router = APIRouter(prefix="/centros", tags=["configuración"])


@router.get("")
def listar_centros(usuario: UsuarioActual, db: Db) -> list[CentroSalida]:
    """Centros activos de la empresa del usuario (para los desplegables de los formularios)."""
    centros = db.scalars(
        select(Centro).where(Centro.empresa_id == usuario.empresa_id, Centro.activo).order_by(Centro.nombre)
    )
    return [CentroSalida.model_validate(c) for c in centros]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_centro(datos: CentroCrear, usuario: SoloAdmin, db: Db) -> CentroSalida:
    """Crea un centro en la empresa del usuario. 409 si ya hay uno con ese nombre."""
    if db.scalar(select(Centro.id).where(Centro.empresa_id == usuario.empresa_id, Centro.nombre == datos.nombre)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un centro llamado '{datos.nombre}'")

    centro = Centro(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(centro)
    db.commit()
    return CentroSalida.model_validate(centro)
