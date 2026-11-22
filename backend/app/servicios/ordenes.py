"""Órdenes de trabajo listas para la API, con sus líneas y su coste (MAN-06).

En bloque: una consulta para las OT (con vehículo, plan y responsable) y otra
para TODAS sus líneas, se listen las que se listen (sin problema N+1).
"""

from collections import defaultdict

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import LineaOT, OrdenTrabajo, Persona, PlanMantenimiento, Vehiculo
from app.reglas.ordenes import Linea, coste
from app.schemas import CosteSalida, LineaSalida, OTSalida


def consulta_base(empresa_id: int) -> Select:  # type: ignore[type-arg]
    return (
        select(OrdenTrabajo, Vehiculo, PlanMantenimiento.nombre, Persona.nombre)
        .join(Vehiculo, Vehiculo.id == OrdenTrabajo.vehiculo_id)
        .outerjoin(PlanMantenimiento, PlanMantenimiento.id == OrdenTrabajo.plan_id)
        .outerjoin(Persona, Persona.id == OrdenTrabajo.responsable_id)
        .where(OrdenTrabajo.empresa_id == empresa_id)
    )


def salidas(db: Session, consulta: Select) -> list[OTSalida]:  # type: ignore[type-arg]
    filas = db.execute(consulta).tuples().all()
    lineas: dict[int, list[LineaOT]] = defaultdict(list)
    if filas:
        for linea in db.scalars(
            select(LineaOT).where(LineaOT.ot_id.in_([ot.id for ot, *_ in filas])).order_by(LineaOT.id)
        ):
            lineas[linea.ot_id].append(linea)

    resultado = []
    for ot, vehiculo, plan_nombre, responsable_nombre in filas:
        reglas = {l.id: Linea(l.concepto, l.cantidad, l.precio_unitario) for l in lineas[ot.id]}
        c = coste(reglas.values())
        resultado.append(
            OTSalida(
                id=ot.id,
                vehiculo_id=vehiculo.id,
                matricula=vehiculo.matricula,
                tipo=ot.tipo,
                origen=ot.origen,
                estado=ot.estado,
                plan_id=ot.plan_id,
                plan_nombre=plan_nombre,
                averia_id=ot.averia_id,
                inmoviliza=ot.inmoviliza,
                descripcion=ot.descripcion,
                responsable_id=ot.responsable_id,
                responsable_nombre=responsable_nombre,
                abierta_en=ot.abierta_en,
                iniciada_en=ot.iniciada_en,
                fecha_cierre=ot.fecha_cierre,
                km_cierre=ot.km_cierre,
                trabajo_realizado=ot.trabajo_realizado,
                cancelada_en=ot.cancelada_en,
                motivo_cancelacion=ot.motivo_cancelacion,
                lineas=[
                    LineaSalida(
                        id=l.id,
                        concepto=l.concepto,
                        recambio_id=l.recambio_id,
                        descripcion=l.descripcion,
                        cantidad=float(l.cantidad),
                        precio_unitario=float(l.precio_unitario),
                        importe=float(reglas[l.id].importe),
                    )
                    for l in lineas[ot.id]
                ],
                coste=CosteSalida(
                    mano_obra=float(c.mano_obra), recambios=float(c.recambios), externos=float(c.externos), total=float(c.total)
                ),
                estado_vehiculo=vehiculo.estado,
            )
        )
    return resultado
