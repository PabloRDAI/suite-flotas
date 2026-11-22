"""Indicadores de mantenimiento (MAN-08) de los vehículos activos, en un periodo.

Definiciones (las mismas que se usan en el cálculo manual de los tests):
- Coste: OT CERRADAS con fecha de cierre en el periodo (suma de sus líneas, con la
  misma función coste() del motor, que redondea cada línea a céntimos).
- Km recorridos: app/reglas/indicadores.py::km_recorridos.
- Coste por km: coste / km recorridos (€/km, 3 decimales).
- Averías: comunicadas en el periodo.
- Días de inmovilización: días distintos en que el vehículo estuvo parado por una
  avería que inmoviliza (de que se comunica a que se resuelve o pasa a una OT) o por
  una OT que inmoviliza (de que se abre a que se cierra o se cancela; si sigue
  abierta, hasta hoy). Ver dias_cubiertos.
- % preventivo: de las OT cerradas (por número y por coste).

En bloque: una consulta por cada tipo de dato, se pidan los vehículos que se pidan.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Averia, LecturaKm, LineaOT, OrdenTrabajo, Vehiculo
from app.reglas.estado_vehiculo import EstadoOT, GravedadAveria
from app.reglas.indicadores import coste_por_km, dias_cubiertos, km_recorridos, porcentaje
from app.reglas.km import Lectura
from app.reglas.ordenes import Linea, TipoOT, coste
from app.schemas import IndicadoresFlota, IndicadoresSalida, IndicadoresVehiculo


def _f(valor: Decimal | None) -> float | None:
    return float(valor) if valor is not None else None


def calcular_indicadores(
    db: Session,
    empresa_id: int,
    desde: date,
    hasta: date,
    hoy: date,
    centro_id: int | None = None,
    tipo_id: int | None = None,
) -> IndicadoresSalida:
    consulta = select(Vehiculo).where(Vehiculo.empresa_id == empresa_id, Vehiculo.activo)
    if centro_id is not None:
        consulta = consulta.where(Vehiculo.centro_id == centro_id)
    if tipo_id is not None:
        consulta = consulta.where(Vehiculo.tipo_id == tipo_id)
    vehiculos = list(db.scalars(consulta.order_by(Vehiculo.matricula)))
    ids = [v.id for v in vehiculos]

    # Lecturas de km (para los km recorridos).
    lecturas: dict[int, list[Lectura]] = defaultdict(list)
    for l in db.scalars(select(LecturaKm).where(LecturaKm.vehiculo_id.in_(ids), LecturaKm.fecha <= hasta)):
        lecturas[l.vehiculo_id].append(Lectura(l.fecha, l.km))

    # OT cerradas en el periodo, con sus líneas (para el coste).
    cerradas = list(
        db.scalars(
            select(OrdenTrabajo).where(
                OrdenTrabajo.vehiculo_id.in_(ids),
                OrdenTrabajo.estado == EstadoOT.CERRADA,
                OrdenTrabajo.fecha_cierre >= desde,
                OrdenTrabajo.fecha_cierre <= hasta,
            )
        )
    )
    lineas: dict[int, list[Linea]] = defaultdict(list)
    for l in db.scalars(select(LineaOT).where(LineaOT.ot_id.in_([o.id for o in cerradas]))):
        lineas[l.ot_id].append(Linea(l.concepto, l.cantidad, l.precio_unitario))
    coste_ot = {o.id: coste(lineas[o.id]).total for o in cerradas}

    # Periodos de inmovilización: OT que inmovilizan…
    intervalos: dict[int, list[tuple[date, date]]] = defaultdict(list)
    primera_ot_de_averia: dict[int, date] = {}
    for o in db.scalars(select(OrdenTrabajo).where(OrdenTrabajo.vehiculo_id.in_(ids))):
        if o.averia_id is not None:
            inicio_ot = o.abierta_en.date()
            primera_ot_de_averia[o.averia_id] = min(primera_ot_de_averia.get(o.averia_id, inicio_ot), inicio_ot)
        if o.inmoviliza:
            fin = o.fecha_cierre or (o.cancelada_en.date() if o.cancelada_en else hoy)
            intervalos[o.vehiculo_id].append((o.abierta_en.date(), fin))

    # …y averías que inmovilizan (hasta que se resuelven o pasan a una OT).
    averias_en_periodo: dict[int, int] = defaultdict(int)
    for a in db.scalars(select(Averia).where(Averia.vehiculo_id.in_(ids))):
        comunicada = a.comunicada_en.date()
        if desde <= comunicada <= hasta:
            averias_en_periodo[a.vehiculo_id] += 1
        if a.gravedad == GravedadAveria.INMOVILIZA:
            finales = [f for f in (a.resuelta_en.date() if a.resuelta_en else None, primera_ot_de_averia.get(a.id)) if f]
            intervalos[a.vehiculo_id].append((comunicada, min(finales) if finales else hoy))

    # Por vehículo.
    filas: list[IndicadoresVehiculo] = []
    por_vehiculo_ot: dict[int, list[OrdenTrabajo]] = defaultdict(list)
    for o in cerradas:
        por_vehiculo_ot[o.vehiculo_id].append(o)
    total_km = 0
    for v in vehiculos:
        ots = por_vehiculo_ot[v.id]
        c = sum((coste_ot[o.id] for o in ots), Decimal("0.00"))
        km = km_recorridos(lecturas[v.id], desde, hasta)
        total_km += km
        filas.append(
            IndicadoresVehiculo(
                vehiculo_id=v.id,
                matricula=v.matricula,
                coste=float(c),
                km_recorridos=km,
                coste_por_km=_f(coste_por_km(c, km)),
                averias=averias_en_periodo[v.id],
                dias_inmovilizado=dias_cubiertos(intervalos[v.id], desde, min(hasta, hoy)),
                ot_preventivas=sum(1 for o in ots if o.tipo == TipoOT.PREVENTIVA),
                ot_correctivas=sum(1 for o in ots if o.tipo == TipoOT.CORRECTIVA),
            )
        )
    filas.sort(key=lambda f: (-f.coste, f.matricula))

    # Flota.
    coste_total = sum(coste_ot.values(), Decimal("0.00"))
    coste_prev = sum((coste_ot[o.id] for o in cerradas if o.tipo == TipoOT.PREVENTIVA), Decimal("0.00"))
    n_prev = sum(1 for o in cerradas if o.tipo == TipoOT.PREVENTIVA)
    flota = IndicadoresFlota(
        coste=float(coste_total),
        coste_preventivo=float(coste_prev),
        coste_correctivo=float(coste_total - coste_prev),
        km_recorridos=total_km,
        coste_por_km=_f(coste_por_km(coste_total, total_km)),
        averias=sum(averias_en_periodo.values()),
        dias_inmovilizado=sum(f.dias_inmovilizado for f in filas),
        ot_cerradas=len(cerradas),
        ot_preventivas=n_prev,
        ot_correctivas=len(cerradas) - n_prev,
        pct_preventivo_ot=_f(porcentaje(n_prev, len(cerradas))),
        pct_preventivo_coste=_f(porcentaje(coste_prev, coste_total)),
    )
    return IndicadoresSalida(desde=desde, hasta=hasta, flota=flota, vehiculos=filas)

