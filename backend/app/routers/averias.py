"""Averías (MAN-03): comunicar (con foto opcional), consultar y resolver.

- Comunicar: CUALQUIER rol (el conductor es quien suele verla). Resolver: gerente y taller.
- "Una avería que inmoviliza cambia el estado del vehículo al instante": se recalcula
  el estado (regla 1) en la misma transacción y la respuesta ya lo trae.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.deps import Db, GestionTaller, UsuarioActual
from app.models import Asignacion, Averia, OrdenTrabajo, Persona, Usuario, Vehiculo
from app.reglas.estado_vehiculo import ESTADOS_OT_ABIERTA, EstadoAveria, GravedadAveria
from app.schemas import AveriaResolver, AveriaSalida, VehiculoSugerido
from app.servicios import adjuntos
from app.servicios.estado_vehiculo import actualizar_estado

router = APIRouter(prefix="/averias", tags=["mantenimiento"])


def _consulta_base(empresa_id: int):  # type: ignore[no-untyped-def]
    return (
        select(Averia, Vehiculo, Usuario.nombre)
        .join(Vehiculo, Vehiculo.id == Averia.vehiculo_id)
        .outerjoin(Usuario, Usuario.id == Averia.comunicada_por_id)
        .where(Averia.empresa_id == empresa_id)
    )


def _ot_de_cada_averia(db: Db, averia_ids: list[int]) -> dict[int, int]:
    """La OT más reciente de cada avería, con UNA consulta para todas (sin N+1)."""
    if not averia_ids:
        return {}
    filas = db.execute(
        select(OrdenTrabajo.averia_id, func.max(OrdenTrabajo.id))
        .where(OrdenTrabajo.averia_id.in_(averia_ids))
        .group_by(OrdenTrabajo.averia_id)
    ).tuples()
    return {averia_id: ot_id for averia_id, ot_id in filas}


def _salida(a: Averia, v: Vehiculo, comunicada_por: str | None, ot_id: int | None = None) -> AveriaSalida:
    return AveriaSalida(
        id=a.id,
        vehiculo_id=v.id,
        matricula=v.matricula,
        comunicada_por=comunicada_por,
        comunicada_en=a.comunicada_en,
        descripcion=a.descripcion,
        gravedad=a.gravedad,
        estado=a.estado,
        tiene_foto=a.foto is not None,
        orden_trabajo_id=ot_id,
        resuelta_en=a.resuelta_en,
        nota_resolucion=a.nota_resolucion,
        estado_vehiculo=v.estado,
    )


def _una(db: Db, empresa_id: int, averia_id: int) -> AveriaSalida:
    fila = db.execute(_consulta_base(empresa_id).where(Averia.id == averia_id)).tuples().one_or_none()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avería no encontrada")
    return _salida(*fila, ot_id=_ot_de_cada_averia(db, [averia_id]).get(averia_id))


# --- Rutas fijas (antes que /{averia_id}) ------------------------------------


@router.get("/vehiculos-sugeridos")
def vehiculos_sugeridos(usuario: UsuarioActual, db: Db) -> list[VehiculoSugerido]:
    """Vehículos asignados HOY a la persona del usuario (habitual primero), para preseleccionar."""
    hoy = date.today()
    filas = db.execute(
        select(Vehiculo, Asignacion.habitual)
        .join(Asignacion, Asignacion.vehiculo_id == Vehiculo.id)
        .join(Persona, Persona.id == Asignacion.persona_id)
        .where(
            Persona.usuario_id == usuario.id,
            Vehiculo.empresa_id == usuario.empresa_id,
            Vehiculo.activo,
            Asignacion.desde <= hoy,
            (Asignacion.hasta.is_(None)) | (Asignacion.hasta >= hoy),
        )
        .order_by(Asignacion.habitual.desc(), Vehiculo.matricula)
    ).tuples()
    return [VehiculoSugerido(id=v.id, matricula=v.matricula, marca=v.marca, modelo=v.modelo, habitual=h) for v, h in filas]


@router.post("", status_code=status.HTTP_201_CREATED)
def comunicar_averia(
    usuario: UsuarioActual,
    db: Db,
    vehiculo_id: Annotated[int, Form()],
    descripcion: Annotated[str, Form(min_length=3, max_length=2000)],
    gravedad: Annotated[GravedadAveria, Form()],
    foto: Annotated[UploadFile | None, File(description="Opcional: JPEG, PNG o WebP de hasta 5 MB")] = None,
) -> AveriaSalida:
    """Comunica una avería (formulario multipart, por la foto). Cualquier rol.

    - 422 si el vehículo no existe en la empresa o está de baja, o si la foto no es válida.
    - 413 si la foto es demasiado grande.
    - Si inmoviliza, el vehículo pasa a "inmovilizado" en esta misma petición.
    """
    descripcion = descripcion.strip()
    if len(descripcion) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Describe la avería (al menos 3 caracteres)")
    vehiculo = db.scalar(
        select(Vehiculo).where(Vehiculo.id == vehiculo_id, Vehiculo.empresa_id == usuario.empresa_id).with_for_update()
    )
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El vehículo no existe o está de baja")

    nombre_foto = None
    if foto is not None and foto.filename:
        try:
            nombre_foto = adjuntos.guardar_foto(foto)
        except adjuntos.AdjuntoNoValido as error:
            codigo = status.HTTP_413_CONTENT_TOO_LARGE if error.demasiado_grande else status.HTTP_422_UNPROCESSABLE_CONTENT
            raise HTTPException(codigo, str(error)) from error

    try:
        averia = Averia(
            empresa_id=usuario.empresa_id,
            vehiculo_id=vehiculo.id,
            comunicada_por_id=usuario.id,
            descripcion=descripcion,
            gravedad=gravedad,
            foto=nombre_foto,
        )
        db.add(averia)
        db.flush()
        actualizar_estado(db, vehiculo)  # regla 1: si inmoviliza, "inmovilizado" ya
        db.commit()
    except Exception:
        if nombre_foto:  # que no quede una foto huérfana si no se pudo guardar la avería
            adjuntos.borrar_foto(nombre_foto)
        raise
    return _una(db, usuario.empresa_id, averia.id)


@router.get("")
def listar_averias(
    usuario: UsuarioActual,
    db: Db,
    abiertas: bool = True,
    vehiculo_id: int | None = None,
    gravedad: GravedadAveria | None = None,
) -> list[AveriaSalida]:
    """Averías de la empresa, de la más reciente a la más antigua. Por defecto, solo las no resueltas."""
    consulta = _consulta_base(usuario.empresa_id)
    if abiertas:
        consulta = consulta.where(Averia.estado != EstadoAveria.RESUELTA)
    if vehiculo_id is not None:
        consulta = consulta.where(Averia.vehiculo_id == vehiculo_id)
    if gravedad is not None:
        consulta = consulta.where(Averia.gravedad == gravedad)
    filas = db.execute(consulta.order_by(Averia.comunicada_en.desc(), Averia.id.desc())).tuples()
    filas = filas.all()
    ots = _ot_de_cada_averia(db, [a.id for a, _, _ in filas])
    return [_salida(a, v, nombre, ots.get(a.id)) for a, v, nombre in filas]


# --- Una avería --------------------------------------------------------------


@router.get("/{averia_id}")
def ver_averia(averia_id: int, usuario: UsuarioActual, db: Db) -> AveriaSalida:
    return _una(db, usuario.empresa_id, averia_id)


@router.get("/{averia_id}/foto", response_class=FileResponse)
def foto_de_la_averia(averia_id: int, usuario: UsuarioActual, db: Db) -> FileResponse:
    """La foto de la avería (con sesión y solo de la propia empresa)."""
    averia = db.scalar(select(Averia).where(Averia.id == averia_id, Averia.empresa_id == usuario.empresa_id))
    if averia is None or averia.foto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto no encontrada")
    ruta = adjuntos.ruta_foto(averia.foto)
    if not ruta.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto no encontrada")
    return FileResponse(ruta, media_type=adjuntos.tipo_mime(averia.foto))


@router.post("/{averia_id}/resolver")
def resolver_averia(averia_id: int, datos: AveriaResolver, usuario: GestionTaller, db: Db) -> AveriaSalida:
    """Resuelve una avería SIN orden de trabajo y recalcula el estado del vehículo.

    409 si ya estaba resuelta o si tiene una OT abierta (entonces se resuelve cerrando la OT).
    """
    averia = db.scalar(select(Averia).where(Averia.id == averia_id, Averia.empresa_id == usuario.empresa_id))
    if averia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avería no encontrada")
    if averia.estado == EstadoAveria.RESUELTA:
        raise HTTPException(status.HTTP_409_CONFLICT, "La avería ya estaba resuelta")
    if db.scalar(
        select(OrdenTrabajo.id).where(OrdenTrabajo.averia_id == averia.id, OrdenTrabajo.estado.in_(ESTADOS_OT_ABIERTA))
    ):
        # Se resuelve cerrando su OT (que además registra km, coste y trabajo realizado).
        raise HTTPException(status.HTTP_409_CONFLICT, "La avería tiene una orden de trabajo abierta: ciérrala para resolverla")

    averia.estado = EstadoAveria.RESUELTA
    averia.resuelta_en = datetime.now(UTC)
    averia.nota_resolucion = datos.nota
    db.flush()
    vehiculo = db.get(Vehiculo, averia.vehiculo_id)
    assert vehiculo is not None
    actualizar_estado(db, vehiculo)
    db.commit()
    return _una(db, usuario.empresa_id, averia.id)
