"""Planes preventivos aplicados a los vehículos (MAN-01).

El cálculo (regla 3) está en app/reglas/preventivo.py; aquí se reúnen los datos
de la BD, se aplica y se guarda.

Desde cuándo se cuenta: al crear un plan (o un vehículo de ese tipo), el sistema
no sabe cuándo se hizo el último mantenimiento, así que empieza a contar desde
HOY y los km actuales. El taller puede registrar después la realización real.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoPlan, PlanMantenimiento, TareaPlan, Vehiculo
from app.reglas.preventivo import Situacion, calcular_proximo, evaluar, urgencia
from app.schemas import PlanSalida, PrevisionItem, PreventivoSalida


def recalcular(estado: EstadoPlan, plan: PlanMantenimiento) -> None:
    """Regla 3: actualiza la próxima fecha y los próximos km a partir del último."""
    proximo = calcular_proximo(estado.ultima_fecha, estado.ultimos_km, plan.intervalo_dias, plan.intervalo_km)
    estado.proxima_fecha = proximo.fecha
    estado.proximos_km = proximo.km


def _nuevo_estado(plan: PlanMantenimiento, vehiculo: Vehiculo, hoy: date) -> EstadoPlan:
    estado = EstadoPlan(
        empresa_id=plan.empresa_id,
        vehiculo_id=vehiculo.id,
        plan_id=plan.id,
        ultima_fecha=hoy,
        ultimos_km=vehiculo.km_actuales,
    )
    recalcular(estado, plan)
    return estado


def crear_estados_para_plan(db: Session, plan: PlanMantenimiento, hoy: date) -> int:
    """Al crear un plan: cada vehículo activo de su tipo empieza a contar desde hoy."""
    con_estado = set(db.scalars(select(EstadoPlan.vehiculo_id).where(EstadoPlan.plan_id == plan.id)))
    vehiculos = db.scalars(
        select(Vehiculo).where(
            Vehiculo.empresa_id == plan.empresa_id, Vehiculo.tipo_id == plan.tipo_vehiculo_id, Vehiculo.activo
        )
    )
    nuevos = [_nuevo_estado(plan, v, hoy) for v in vehiculos if v.id not in con_estado]
    db.add_all(nuevos)
    return len(nuevos)


def sincronizar_vehiculo(db: Session, vehiculo: Vehiculo, hoy: date) -> None:
    """Al crear un vehículo o cambiarle el tipo: que tenga estado en los planes de su tipo."""
    planes = db.scalars(
        select(PlanMantenimiento).where(
            PlanMantenimiento.empresa_id == vehiculo.empresa_id,
            PlanMantenimiento.tipo_vehiculo_id == vehiculo.tipo_id,
            PlanMantenimiento.activo,
        )
    )
    con_estado = set(db.scalars(select(EstadoPlan.plan_id).where(EstadoPlan.vehiculo_id == vehiculo.id)))
    db.add_all(_nuevo_estado(p, vehiculo, hoy) for p in planes if p.id not in con_estado)


def tareas_de(db: Session, plan_ids: list[int]) -> dict[int, list[str]]:
    """Tareas de varios planes con una consulta, en su orden."""
    resultado: dict[int, list[str]] = defaultdict(list)
    if plan_ids:
        for t in db.scalars(select(TareaPlan).where(TareaPlan.plan_id.in_(plan_ids)).order_by(TareaPlan.orden)):
            resultado[t.plan_id].append(t.descripcion)
    return resultado


def salida_plan(plan: PlanMantenimiento, tareas: list[str]) -> PlanSalida:
    return PlanSalida(
        id=plan.id,
        nombre=plan.nombre,
        tipo_vehiculo_id=plan.tipo_vehiculo_id,
        intervalo_km=plan.intervalo_km,
        intervalo_dias=plan.intervalo_dias,
        activo=plan.activo,
        tareas=tareas,
    )


def preventivos_de(db: Session, vehiculo: Vehiculo, hoy: date) -> list[PreventivoSalida]:
    """Planes activos del tipo del vehículo con su situación: lo más urgente primero."""
    filas = db.execute(
        select(EstadoPlan, PlanMantenimiento)
        .join(PlanMantenimiento, PlanMantenimiento.id == EstadoPlan.plan_id)
        .where(
            EstadoPlan.vehiculo_id == vehiculo.id,
            PlanMantenimiento.activo,
            PlanMantenimiento.tipo_vehiculo_id == vehiculo.tipo_id,  # si cambió de tipo, los antiguos no cuentan
        )
    ).tuples().all()
    tareas = tareas_de(db, [p.id for _, p in filas])

    resultado = []
    for estado, plan in filas:
        proximo = calcular_proximo(estado.ultima_fecha, estado.ultimos_km, plan.intervalo_dias, plan.intervalo_km)
        e = evaluar(proximo, hoy, vehiculo.km_actuales)
        resultado.append(
            PreventivoSalida(
                plan_id=plan.id,
                plan_nombre=plan.nombre,
                intervalo_km=plan.intervalo_km,
                intervalo_dias=plan.intervalo_dias,
                tareas=tareas[plan.id],
                ultima_fecha=estado.ultima_fecha,
                ultimos_km=estado.ultimos_km,
                proxima_fecha=proximo.fecha,
                proximos_km=proximo.km,
                situacion=e.situacion,
                motivo=e.motivo,
                dias_restantes=e.dias_restantes,
                km_restantes=e.km_restantes,
                vencido_por_fecha=e.vencido_por_fecha,
                vencido_por_km=e.vencido_por_km,
            )
        )
    orden = {"vencido": 0, "proximo": 1, "al_dia": 2}
    resultado.sort(key=lambda p: (orden[p.situacion], p.plan_nombre))
    return resultado


def prevision(
    db: Session,
    empresa_id: int,
    hoy: date,
    centro_id: int | None = None,
    tipo_id: int | None = None,
    vehiculo_ids: list[int] | None = None,
) -> list[PrevisionItem]:
    """MAN-02: preventivos vencidos o próximos (30 días o 2.000 km) de la empresa,
    ordenados por urgencia (app/reglas/preventivo.py::urgencia).

    Una consulta para todos los preventivos (más otra para las tareas).
    """
    consulta = (
        select(EstadoPlan, PlanMantenimiento, Vehiculo)
        .join(PlanMantenimiento, PlanMantenimiento.id == EstadoPlan.plan_id)
        .join(Vehiculo, Vehiculo.id == EstadoPlan.vehiculo_id)
        .where(
            Vehiculo.empresa_id == empresa_id,
            Vehiculo.activo,
            PlanMantenimiento.activo,
            PlanMantenimiento.tipo_vehiculo_id == Vehiculo.tipo_id,
        )
    )
    if centro_id is not None:
        consulta = consulta.where(Vehiculo.centro_id == centro_id)
    if tipo_id is not None:
        consulta = consulta.where(Vehiculo.tipo_id == tipo_id)
    if vehiculo_ids is not None:
        consulta = consulta.where(Vehiculo.id.in_(vehiculo_ids))

    pendientes = []
    for estado, plan, vehiculo in db.execute(consulta).tuples():
        e = evaluar(
            calcular_proximo(estado.ultima_fecha, estado.ultimos_km, plan.intervalo_dias, plan.intervalo_km),
            hoy,
            vehiculo.km_actuales,
        )
        if e.situacion != Situacion.AL_DIA:
            pendientes.append((estado, plan, vehiculo, e))

    tareas = tareas_de(db, list({plan.id for _, plan, _, _ in pendientes}))
    items = [
        PrevisionItem(
            vehiculo_id=v.id,
            matricula=v.matricula,
            tipo_id=v.tipo_id,
            centro_id=v.centro_id,
            km_actuales=v.km_actuales,
            plan_id=p.id,
            plan_nombre=p.nombre,
            tareas=tareas[p.id],
            situacion=e.situacion,
            motivo=e.motivo,
            proxima_fecha=est.proxima_fecha,
            proximos_km=est.proximos_km,
            dias_restantes=e.dias_restantes,
            km_restantes=e.km_restantes,
            urgencia=urgencia(e),
        )
        for est, p, v, e in pendientes
    ]
    # Lo más urgente primero; a igual urgencia, por matrícula y plan (orden estable).
    items.sort(key=lambda i: (i.urgencia, i.matricula, i.plan_nombre))
    return items
