"""Asignaciones conductor-vehículo (PER-03) con avisos de documentación (PER-04).

- Consultar: cualquier rol. Asignar, finalizar y borrar: admin y tráfico.
- PER-03: como máximo un conductor HABITUAL por vehículo a la vez (regla en
  app/reglas/asignaciones.py y, como última barrera, restricción de exclusión en la BD).
- PER-04: si la documentación del conductor está caducada, se AVISA pero no se bloquea.
"""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import Db, GestionFlota, UsuarioActual
from app.models import AplicaA, Asignacion, Persona, Puesto, Vehiculo
from app.reglas.asignaciones import AsignacionExistente, AsignacionNoValida, Periodo, comprobar_habitual
from app.routers.personas import persona_de_mi_empresa
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.schemas import AsignacionCrear, AsignacionFinalizar, AsignacionSalida
from app.servicios import asignaciones as servicio
from app.servicios.vencimientos import documentos_en_bloque

router = APIRouter(tags=["personal"])


def _asignacion_de_mi_empresa(db: Db, empresa_id: int, asignacion_id: int) -> Asignacion:
    asignacion = db.scalar(
        select(Asignacion).where(Asignacion.id == asignacion_id, Asignacion.empresa_id == empresa_id)
    )
    if asignacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asignación no encontrada")
    return asignacion


def _una(db: Db, empresa_id: int, asignacion_id: int) -> AsignacionSalida:
    """La asignación ya preparada para la respuesta (con sus avisos)."""
    a, nombre, matricula = db.execute(
        select(Asignacion, Persona.nombre, Vehiculo.matricula)
        .join(Persona, Persona.id == Asignacion.persona_id)
        .join(Vehiculo, Vehiculo.id == Asignacion.vehiculo_id)
        .where(Asignacion.id == asignacion_id, Asignacion.empresa_id == empresa_id)
    ).one()
    documentos = documentos_en_bloque(db, empresa_id, AplicaA.PERSONA, [a.persona_id])
    return servicio.salida(a, nombre, matricula, documentos[a.persona_id], date.today())


# --- Consultas ---------------------------------------------------------------


@router.get("/vehiculos/{vehiculo_id}/asignaciones")
def asignaciones_del_vehiculo(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> list[AsignacionSalida]:
    """Historial de conductores del vehículo (también si está de baja)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    return servicio.listar(db, usuario.empresa_id, date.today(), vehiculo_id=vehiculo.id)


@router.get("/personas/{persona_id}/asignaciones")
def asignaciones_de_la_persona(persona_id: int, usuario: UsuarioActual, db: Db) -> list[AsignacionSalida]:
    """Historial de vehículos de la persona (también si está de baja)."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=False)
    return servicio.listar(db, usuario.empresa_id, date.today(), persona_id=persona.id)


# --- Cambios -----------------------------------------------------------------


@router.post("/asignaciones", status_code=status.HTTP_201_CREATED)
def asignar(datos: AsignacionCrear, usuario: GestionFlota, db: Db) -> AsignacionSalida:
    """Asigna un conductor a un vehículo.

    - 409 si ya hay otro conductor HABITUAL en esas fechas (PER-03).
    - 422 si la persona no es conductor/a activo/a o el vehículo no está activo.
    - La respuesta incluye "avisos" si su documentación está caducada (PER-04): avisa, no bloquea.
    """
    persona = db.scalar(
        select(Persona).where(Persona.id == datos.persona_id, Persona.empresa_id == usuario.empresa_id)
    )
    if persona is None or not persona.activo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La persona no existe o está de baja")
    if persona.puesto != Puesto.CONDUCTOR:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{persona.nombre} no tiene puesto de conductor/a")

    # Bloqueo del vehículo: dos asignaciones simultáneas al mismo vehículo se validan por turnos.
    vehiculo = db.scalar(
        select(Vehiculo)
        .where(Vehiculo.id == datos.vehiculo_id, Vehiculo.empresa_id == usuario.empresa_id)
        .with_for_update()
    )
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El vehículo no existe o está de baja")

    desde = datos.desde or date.today()
    if datos.hasta is not None and datos.hasta < desde:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha de fin no puede ser anterior a la de inicio")

    existentes = db.execute(
        select(Asignacion, Persona.nombre)
        .join(Persona, Persona.id == Asignacion.persona_id)
        .where(Asignacion.vehiculo_id == vehiculo.id)
    ).tuples()
    try:
        comprobar_habitual(
            Periodo(desde, datos.hasta),
            datos.habitual,
            [AsignacionExistente(nombre, Periodo(a.desde, a.hasta), a.habitual) for a, nombre in existentes],
        )
    except AsignacionNoValida as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    asignacion = Asignacion(
        empresa_id=usuario.empresa_id,
        persona_id=persona.id,
        vehiculo_id=vehiculo.id,
        desde=desde,
        hasta=datos.hasta,
        habitual=datos.habitual,
        notas=datos.notas,
        registrado_por_id=usuario.id,
    )
    db.add(asignacion)
    try:
        db.commit()
    except IntegrityError as error:  # la restricción de exclusión de la BD (última barrera)
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El vehículo ya tiene un conductor habitual en esas fechas") from error
    return _una(db, usuario.empresa_id, asignacion.id)


@router.post("/asignaciones/{asignacion_id}/finalizar")
def finalizar(asignacion_id: int, datos: AsignacionFinalizar, usuario: GestionFlota, db: Db) -> AsignacionSalida:
    """Pone fecha de fin a una asignación vigente (el historial se conserva).

    Sin fecha, termina AYER: así el nuevo conductor habitual puede empezar hoy.
    (Si empezó hoy mismo, termina hoy.) 409 si ya tenía fecha de fin.
    """
    asignacion = _asignacion_de_mi_empresa(db, usuario.empresa_id, asignacion_id)
    if asignacion.hasta is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta asignación ya tiene fecha de fin")

    hasta = datos.hasta or max(asignacion.desde, date.today() - timedelta(days=1))
    if hasta < asignacion.desde:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha de fin no puede ser anterior a la de inicio")
    asignacion.hasta = hasta
    db.commit()
    return _una(db, usuario.empresa_id, asignacion.id)


@router.delete("/asignaciones/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(asignacion_id: int, usuario: GestionFlota, db: Db) -> Response:
    """Borra una asignación registrada por error. (Para terminar una real, usa finalizar.)"""
    asignacion = _asignacion_de_mi_empresa(db, usuario.empresa_id, asignacion_id)
    db.delete(asignacion)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
