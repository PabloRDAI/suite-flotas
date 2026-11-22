"""Catálogo de recambios (MAN-09): referencia, nombre y precio. Sin stock.

- Consultar: cualquier rol. Alta, edición y baja: gerente y jefe de taller (GestionTaller).
- La baja es lógica: el recambio deja de ofrecerse, pero las OT antiguas lo conservan.
"""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.deps import Db, GestionTaller, UsuarioActual
from app.models import Recambio, Usuario
from app.schemas import RecambioCrear, RecambioEditar, RecambioSalida

router = APIRouter(prefix="/recambios", tags=["recambios"])


def consultar_recambios(db: Db, usuario: Usuario, buscar: str | None = None, incluir_bajas: bool = False) -> list[Recambio]:
    """La misma consulta para el listado y para la exportación (GEN-06): mismos filtros."""
    consulta = select(Recambio).where(Recambio.empresa_id == usuario.empresa_id)
    if not incluir_bajas:
        consulta = consulta.where(Recambio.activo)
    if buscar:
        patron = f"%{buscar.strip()}%"
        consulta = consulta.where(or_(Recambio.referencia.ilike(patron), Recambio.nombre.ilike(patron)))
    return list(db.scalars(consulta.order_by(Recambio.nombre, Recambio.referencia)))


def _recambio_de_mi_empresa(db: Db, usuario: Usuario, recambio_id: int) -> Recambio:
    recambio = db.scalar(select(Recambio).where(Recambio.id == recambio_id, Recambio.empresa_id == usuario.empresa_id))
    if recambio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recambio no encontrado")
    return recambio


def _comprobar_referencia_libre(db: Db, usuario: Usuario, referencia: str, excepto_id: int | None = None) -> None:
    consulta = select(Recambio).where(Recambio.empresa_id == usuario.empresa_id, Recambio.referencia == referencia)
    if excepto_id is not None:
        consulta = consulta.where(Recambio.id != excepto_id)
    otro = db.scalar(consulta)
    if otro is not None:
        detalle = f"Ya existe un recambio con la referencia {referencia}"
        raise HTTPException(status.HTTP_409_CONFLICT, detalle + (" (está dado de baja)" if not otro.activo else ""))


def _guardar(db: Db) -> None:
    try:
        db.commit()
    except IntegrityError as error:  # dos altas simultáneas con la misma referencia
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un recambio con esa referencia") from error


@router.get("")
def listar_recambios(
    usuario: UsuarioActual, db: Db, buscar: str | None = None, incluir_bajas: bool = False
) -> list[RecambioSalida]:
    """Catálogo ordenado por nombre. ?buscar=… filtra por referencia o nombre."""
    return [RecambioSalida.model_validate(r) for r in consultar_recambios(db, usuario, buscar, incluir_bajas)]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_recambio(datos: RecambioCrear, usuario: GestionTaller, db: Db) -> RecambioSalida:
    _comprobar_referencia_libre(db, usuario, datos.referencia)
    recambio = Recambio(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(recambio)
    _guardar(db)
    return RecambioSalida.model_validate(recambio)


@router.patch("/{recambio_id}")
def editar_recambio(recambio_id: int, datos: RecambioEditar, usuario: GestionTaller, db: Db) -> RecambioSalida:
    """Edición parcial. El precio nuevo se usa a partir de ahora; las OT ya registradas no cambian."""
    recambio = _recambio_de_mi_empresa(db, usuario, recambio_id)
    cambios = datos.model_dump(exclude_unset=True)
    if "referencia" in cambios:
        _comprobar_referencia_libre(db, usuario, cambios["referencia"], excepto_id=recambio.id)
    for campo, valor in cambios.items():
        setattr(recambio, campo, valor)
    _guardar(db)
    return RecambioSalida.model_validate(recambio)


@router.delete("/{recambio_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_recambio(recambio_id: int, usuario: GestionTaller, db: Db) -> Response:
    """Baja lógica: deja de aparecer en el catálogo; las OT que lo usaron no cambian."""
    recambio = _recambio_de_mi_empresa(db, usuario, recambio_id)
    recambio.activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
