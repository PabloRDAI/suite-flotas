"""Planes de mantenimiento preventivo (MAN-01) y su situación en cada vehículo.

- Consultar: cualquier rol. Crear, editar, dar de baja y registrar realizaciones:
  gerente y jefe de taller (spec: "Jefe de taller: gestiona … planes de mantenimiento").
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select

from app.deps import Db, GestionTaller, UsuarioActual
from app.models import EstadoPlan, PlanMantenimiento, TareaPlan, TipoVehiculo, Usuario
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.schemas import PlanCrear, PlanEditar, PlanSalida, PrevisionItem, PreventivoSalida, RealizacionCrear
from app.servicios import preventivos as servicio
from app.servicios.etiquetas import etiqueta
from app.servicios.excel import Columna, libro_xlsx, respuesta_xlsx

router = APIRouter(tags=["mantenimiento"])


def _plan_de_mi_empresa(db: Db, usuario: Usuario, plan_id: int) -> PlanMantenimiento:
    plan = db.scalar(
        select(PlanMantenimiento).where(PlanMantenimiento.id == plan_id, PlanMantenimiento.empresa_id == usuario.empresa_id)
    )
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    return plan


def _comprobar_nombre_libre(db: Db, plan: PlanMantenimiento | None, empresa_id: int, tipo_id: int, nombre: str) -> None:
    consulta = select(PlanMantenimiento.id).where(
        PlanMantenimiento.empresa_id == empresa_id,
        PlanMantenimiento.tipo_vehiculo_id == tipo_id,
        PlanMantenimiento.nombre == nombre,
    )
    if plan is not None:
        consulta = consulta.where(PlanMantenimiento.id != plan.id)
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya hay un plan llamado '{nombre}' para ese tipo de vehículo")


def _guardar_tareas(db: Db, plan: PlanMantenimiento, tareas: list[str]) -> None:
    """Sustituye la lista de tareas del plan."""
    db.execute(delete(TareaPlan).where(TareaPlan.plan_id == plan.id))
    db.add_all(
        TareaPlan(empresa_id=plan.empresa_id, plan_id=plan.id, orden=n, descripcion=d)
        for n, d in enumerate(tareas, start=1)
    )


def _salida(db: Db, plan: PlanMantenimiento) -> PlanSalida:
    return servicio.salida_plan(plan, servicio.tareas_de(db, [plan.id])[plan.id])


# --- Planes ------------------------------------------------------------------


@router.get("/planes")
def listar_planes(usuario: UsuarioActual, db: Db, tipo_vehiculo_id: int | None = None) -> list[PlanSalida]:
    consulta = select(PlanMantenimiento).where(PlanMantenimiento.empresa_id == usuario.empresa_id, PlanMantenimiento.activo)
    if tipo_vehiculo_id is not None:
        consulta = consulta.where(PlanMantenimiento.tipo_vehiculo_id == tipo_vehiculo_id)
    planes = list(db.scalars(consulta.order_by(PlanMantenimiento.nombre)))
    tareas = servicio.tareas_de(db, [p.id for p in planes])
    return [servicio.salida_plan(p, tareas[p.id]) for p in planes]


@router.post("/planes", status_code=status.HTTP_201_CREATED)
def crear_plan(datos: PlanCrear, usuario: GestionTaller, db: Db) -> PlanSalida:
    """Crea el plan y pone a contar desde hoy a todos los vehículos activos de su tipo."""
    if not db.scalar(
        select(TipoVehiculo.id).where(TipoVehiculo.id == datos.tipo_vehiculo_id, TipoVehiculo.empresa_id == usuario.empresa_id)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El tipo de vehículo no existe en tu empresa")
    _comprobar_nombre_libre(db, None, usuario.empresa_id, datos.tipo_vehiculo_id, datos.nombre)

    plan = PlanMantenimiento(empresa_id=usuario.empresa_id, **datos.model_dump(exclude={"tareas"}))
    db.add(plan)
    db.flush()
    _guardar_tareas(db, plan, datos.tareas)
    servicio.crear_estados_para_plan(db, plan, date.today())
    db.commit()
    return _salida(db, plan)


@router.get("/planes/{plan_id}")
def ver_plan(plan_id: int, usuario: UsuarioActual, db: Db) -> PlanSalida:
    return _salida(db, _plan_de_mi_empresa(db, usuario, plan_id))


@router.patch("/planes/{plan_id}")
def editar_plan(plan_id: int, datos: PlanEditar, usuario: GestionTaller, db: Db) -> PlanSalida:
    """Cambia nombre, intervalos o tareas. Si cambian los intervalos, se recalcula el
    próximo de todos los vehículos (el último realizado no cambia)."""
    plan = _plan_de_mi_empresa(db, usuario, plan_id)
    if not plan.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    cambios = datos.model_dump(exclude_unset=True)

    if "nombre" in cambios:
        _comprobar_nombre_libre(db, plan, usuario.empresa_id, plan.tipo_vehiculo_id, cambios["nombre"])
    km = cambios.get("intervalo_km", plan.intervalo_km)
    dias = cambios.get("intervalo_dias", plan.intervalo_dias)
    if km is None and dias is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El plan debe conservar al menos un intervalo")

    if "nombre" in cambios:
        plan.nombre = cambios["nombre"]
    if "tareas" in cambios:
        _guardar_tareas(db, plan, cambios["tareas"])
    if (km, dias) != (plan.intervalo_km, plan.intervalo_dias):
        plan.intervalo_km, plan.intervalo_dias = km, dias
        for estado in db.scalars(select(EstadoPlan).where(EstadoPlan.plan_id == plan.id)):
            servicio.recalcular(estado, plan)
    db.commit()
    return _salida(db, plan)


@router.delete("/planes/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_plan(plan_id: int, usuario: GestionTaller, db: Db) -> Response:
    """Baja lógica: el plan deja de aplicarse, pero se conserva (y su historial)."""
    plan = _plan_de_mi_empresa(db, usuario, plan_id)
    if not plan.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    plan.activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Previsión de preventivos (MAN-02) ---------------------------------------


@router.get("/preventivos/prevision")
def prevision_de_preventivos(
    usuario: UsuarioActual, db: Db, centro_id: int | None = None, tipo_id: int | None = None
) -> list[PrevisionItem]:
    """Lo que toca en los próximos 30 días o 2.000 km (y lo ya vencido), por urgencia."""
    return servicio.prevision(db, usuario.empresa_id, date.today(), centro_id=centro_id, tipo_id=tipo_id)


@router.get("/preventivos/prevision/exportar")
def exportar_prevision(usuario: UsuarioActual, db: Db, centro_id: int | None = None, tipo_id: int | None = None) -> Response:
    """GEN-06: la previsión de preventivos en Excel, por urgencia y con los mismos filtros."""
    columnas = [
        Columna("Matrícula", 12), Columna("Plan", 24), Columna("Situación", 11), Columna("Motivo", 40),
        Columna("Próxima fecha", 13, "fecha"), Columna("Días restantes", 13, "entero"), Columna("Próximos km", 13, "entero"),
        Columna("Km restantes", 13, "entero"), Columna("Km actuales", 12, "entero"), Columna("Tareas", 50),
    ]
    filas = [
        [p.matricula, p.plan_nombre, etiqueta(p.situacion), p.motivo, p.proxima_fecha, p.dias_restantes, p.proximos_km,
         p.km_restantes, p.km_actuales, "; ".join(p.tareas)]
        for p in prevision_de_preventivos(usuario, db, centro_id=centro_id, tipo_id=tipo_id)
    ]
    return respuesta_xlsx(libro_xlsx("Previsión", columnas, filas), "prevision-preventivos")


# --- Preventivos de un vehículo ----------------------------------------------


@router.get("/vehiculos/{vehiculo_id}/preventivos")
def preventivos_del_vehiculo(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> list[PreventivoSalida]:
    """Situación de cada plan en el vehículo (vencidos primero), con el motivo."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    return servicio.preventivos_de(db, vehiculo, date.today())


@router.post("/vehiculos/{vehiculo_id}/preventivos/{plan_id}/realizado")
def registrar_realizacion(
    vehiculo_id: int, plan_id: int, datos: RealizacionCrear, usuario: GestionTaller, db: Db
) -> list[PreventivoSalida]:
    """Registra que se hizo el preventivo y recalcula el próximo.

    Sin datos: hoy y con los km actuales. La fecha no puede ser futura ni los km
    mayores que los actuales del vehículo (422).
    """
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    fila = db.execute(
        select(EstadoPlan, PlanMantenimiento)
        .join(PlanMantenimiento, PlanMantenimiento.id == EstadoPlan.plan_id)
        .where(
            EstadoPlan.vehiculo_id == vehiculo.id,
            EstadoPlan.plan_id == plan_id,
            PlanMantenimiento.activo,
            PlanMantenimiento.tipo_vehiculo_id == vehiculo.tipo_id,
        )
    ).tuples().one_or_none()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese plan no se aplica a este vehículo")
    estado, plan = fila

    hoy = date.today()
    fecha = datos.fecha or hoy
    km = datos.km if datos.km is not None else vehiculo.km_actuales
    if fecha > hoy:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha no puede ser futura")
    if km > vehiculo.km_actuales:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Los km ({km}) no pueden superar los actuales del vehículo ({vehiculo.km_actuales})",
        )

    estado.ultima_fecha, estado.ultimos_km = fecha, km
    servicio.recalcular(estado, plan)
    db.commit()
    return servicio.preventivos_de(db, vehiculo, hoy)
