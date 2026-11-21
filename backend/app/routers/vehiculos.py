"""Vehículos: alta, consulta, edición y baja lógica (FLO-01), con permisos (GEN-01, GEN-02).

Reglas comunes a todos los endpoints:
- Todo se filtra por la empresa del usuario (GEN-01). Un vehículo de otra
  empresa responde 404, igual que uno que no existe: no se revela que existe.
- Alta, edición y baja: solo admin y tráfico (GestionFlota). Consulta: cualquier rol.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import Db, GestionFlota, UsuarioActual
from app.models import Centro, LecturaKm, TipoVehiculo, Usuario, Vehiculo
from app.schemas import VehiculoCrear, VehiculoEditar, VehiculoSalida
from app.servicios.estado_vehiculo import actualizar_estado

router = APIRouter(prefix="/vehiculos", tags=["vehículos"])


# --- Funciones auxiliares ----------------------------------------------------


def vehiculo_de_mi_empresa(
    db: Db, usuario: Usuario, vehiculo_id: int, solo_activos: bool, bloquear: bool = False
) -> Vehiculo:
    """Devuelve el vehículo si es de la empresa del usuario; si no, 404.

    bloquear=True hace SELECT ... FOR UPDATE: nadie más puede modificar este
    vehículo hasta que termine la transacción. Evita que dos peticiones
    simultáneas validen a la vez con datos que la otra está cambiando.
    """
    consulta = select(Vehiculo).where(Vehiculo.id == vehiculo_id, Vehiculo.empresa_id == usuario.empresa_id)
    if bloquear:
        consulta = consulta.with_for_update()
    vehiculo = db.scalar(consulta)
    if vehiculo is None or (solo_activos and not vehiculo.activo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehículo no encontrado")
    return vehiculo


def _comprobar_centro_y_tipo(db: Db, usuario: Usuario, centro_id: int | None, tipo_id: int | None) -> None:
    """422 si el centro o el tipo no existen (activos) en la empresa del usuario.

    La BD también lo impide (FK compuestas), pero así el mensaje es claro.
    """
    if centro_id is not None and not db.scalar(
        select(Centro.id).where(Centro.id == centro_id, Centro.empresa_id == usuario.empresa_id, Centro.activo)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El centro indicado no existe en tu empresa")
    if tipo_id is not None and not db.scalar(
        select(TipoVehiculo.id).where(
            TipoVehiculo.id == tipo_id, TipoVehiculo.empresa_id == usuario.empresa_id, TipoVehiculo.activo
        )
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "El tipo de vehículo indicado no existe en tu empresa"
        )


def _comprobar_matricula_libre(db: Db, usuario: Usuario, matricula: str, excepto_id: int | None = None) -> None:
    """409 si otro vehículo de la empresa (activo o dado de baja) ya usa esa matrícula (FLO-01)."""
    consulta = select(Vehiculo).where(Vehiculo.empresa_id == usuario.empresa_id, Vehiculo.matricula == matricula)
    if excepto_id is not None:
        consulta = consulta.where(Vehiculo.id != excepto_id)
    otro = db.scalar(consulta)
    if otro is not None:
        detalle = f"Ya existe un vehículo con la matrícula {matricula}"
        if not otro.activo:
            detalle += " (está dado de baja)"
        raise HTTPException(status.HTTP_409_CONFLICT, detalle)


def _guardar(db: Db, solo_flush: bool = False) -> None:
    """Envía los cambios a la BD (y los confirma, salvo solo_flush=True).

    Si la BD detecta un duplicado que se coló (dos altas simultáneas con la
    misma matrícula), responde 409 en vez de un error 500.
    """
    try:
        db.flush() if solo_flush else db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un vehículo con esa matrícula") from error


# --- Endpoints ---------------------------------------------------------------


@router.get("")
def listar_vehiculos(
    usuario: UsuarioActual,
    db: Db,
    centro_id: int | None = None,
    tipo_id: int | None = None,
    incluir_bajas: bool = False,
) -> list[VehiculoSalida]:
    """Vehículos de la empresa del usuario, ordenados por matrícula.

    Filtros opcionales: ?centro_id=…, ?tipo_id=… y ?incluir_bajas=true.
    """
    # GEN-01: SIEMPRE filtrar por la empresa del usuario conectado.
    consulta = select(Vehiculo).where(Vehiculo.empresa_id == usuario.empresa_id)
    if not incluir_bajas:
        consulta = consulta.where(Vehiculo.activo)
    if centro_id is not None:
        consulta = consulta.where(Vehiculo.centro_id == centro_id)
    if tipo_id is not None:
        consulta = consulta.where(Vehiculo.tipo_id == tipo_id)
    return [VehiculoSalida.model_validate(v) for v in db.scalars(consulta.order_by(Vehiculo.matricula))]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_vehiculo(datos: VehiculoCrear, usuario: GestionFlota, db: Db) -> VehiculoSalida:
    """Alta de vehículo en la empresa del usuario. Empieza como "operativo".

    Se crea también su lectura de km inicial (FLO-05): así los km actuales
    salen siempre de una lectura, también los del alta.

    - 409 si la matrícula ya existe en la empresa.
    - 422 si los datos no son válidos o el centro/tipo no son de la empresa.
    """
    _comprobar_centro_y_tipo(db, usuario, datos.centro_id, datos.tipo_id)
    _comprobar_matricula_libre(db, usuario, datos.matricula)

    vehiculo = Vehiculo(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(vehiculo)
    _guardar(db, solo_flush=True)  # INSERT ya, para conocer vehiculo.id

    db.add(
        LecturaKm(
            empresa_id=usuario.empresa_id,
            vehiculo_id=vehiculo.id,
            fecha=date.today(),
            km=vehiculo.km_actuales,
            registrada_por_id=usuario.id,
        )
    )
    db.commit()
    return VehiculoSalida.model_validate(vehiculo)


@router.get("/{vehiculo_id}")
def ver_vehiculo(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> VehiculoSalida:
    """Ficha de un vehículo (también si está dado de baja, para consultar su historial)."""
    return VehiculoSalida.model_validate(vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False))


@router.patch("/{vehiculo_id}")
def editar_vehiculo(vehiculo_id: int, datos: VehiculoEditar, usuario: GestionFlota, db: Db) -> VehiculoSalida:
    """Edición parcial: solo cambia los campos enviados. Un vehículo dado de baja no se edita (404)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    # exclude_unset: solo los campos que el cliente envió (no los que quedan a None por defecto).
    cambios = datos.model_dump(exclude_unset=True)

    _comprobar_centro_y_tipo(db, usuario, cambios.get("centro_id"), cambios.get("tipo_id"))
    if "matricula" in cambios:
        _comprobar_matricula_libre(db, usuario, cambios["matricula"], excepto_id=vehiculo.id)

    for campo, valor in cambios.items():
        setattr(vehiculo, campo, valor)
    _guardar(db)
    return VehiculoSalida.model_validate(vehiculo)


@router.delete("/{vehiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_vehiculo(vehiculo_id: int, usuario: GestionFlota, db: Db) -> Response:
    """Baja lógica (FLO-01): el vehículo no se borra, se marca como inactivo y "de baja".

    - 403 si el rol no puede gestionar la flota (p. ej. un conductor).
    - 404 si no existe, es de otra empresa o ya estaba dado de baja.
    """
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    vehiculo.activo = False
    actualizar_estado(db, vehiculo)  # regla 1: inactivo -> "de baja"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
