"""Tipos de vencimiento configurables por cada empresa (FLO-06; PER-02 más adelante)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import Db, SoloAdmin, UsuarioActual
from app.models import AplicaA, TipoVencimiento
from app.schemas import TipoVencimientoCrear, TipoVencimientoSalida

router = APIRouter(prefix="/tipos-vencimiento", tags=["configuración"])


@router.get("")
def listar_tipos(usuario: UsuarioActual, db: Db, aplica_a: AplicaA | None = None) -> list[TipoVencimientoSalida]:
    """Tipos activos de la empresa; ?aplica_a=vehiculo o ?aplica_a=persona para filtrar."""
    consulta = select(TipoVencimiento).where(
        TipoVencimiento.empresa_id == usuario.empresa_id, TipoVencimiento.activo
    )
    if aplica_a is not None:
        consulta = consulta.where(TipoVencimiento.aplica_a == aplica_a)
    return [TipoVencimientoSalida.model_validate(t) for t in db.scalars(consulta.order_by(TipoVencimiento.nombre))]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_tipo(datos: TipoVencimientoCrear, usuario: SoloAdmin, db: Db) -> TipoVencimientoSalida:
    """Crea un tipo (p. ej. "ITV" con 30 días de aviso). 409 si ya existe con ese nombre."""
    existe = db.scalar(
        select(TipoVencimiento.id).where(
            TipoVencimiento.empresa_id == usuario.empresa_id,
            TipoVencimiento.aplica_a == datos.aplica_a,
            TipoVencimiento.nombre == datos.nombre,
        )
    )
    if existe:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un tipo de vencimiento llamado '{datos.nombre}'")

    tipo = TipoVencimiento(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(tipo)
    db.commit()
    return TipoVencimientoSalida.model_validate(tipo)
