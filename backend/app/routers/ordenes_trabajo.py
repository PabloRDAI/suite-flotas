"""Órdenes de trabajo (MAN-04 a MAN-06).

- Consultar: cualquier rol. Crear, cambiar de estado y editar líneas: gerente y taller.
- MAN-04: se crean desde una avería (que pasa a "en reparación"), desde un plan o a mano.
- MAN-05: abierta -> en curso -> cerrada (o cancelada). Al cerrar se exigen los km y la
  fecha: los km se registran como lectura (FLO-05) y, si es preventiva, el plan recalcula
  el próximo. Las reglas del flujo y del coste están en app/reglas/ordenes.py.
- Tras cada cambio se recalcula el estado del vehículo (regla 1: "en taller" si inmoviliza).
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, GestionTaller, UsuarioActual
from app.models import Averia, EstadoPlan, LecturaKm, LineaOT, OrdenTrabajo, Persona, PlanMantenimiento, Vehiculo
from app.reglas.estado_vehiculo import ESTADOS_OT_ABIERTA, EstadoAveria, EstadoOT, GravedadAveria
from app.reglas.km import Lectura, LecturaNoValida, comprobar_lectura, km_actuales
from app.reglas.ordenes import OrigenOT, TipoOT, TransicionNoValida, comprobar_transicion, editable
from app.schemas import (
    HistorialItem,
    HistorialSalida,
    LineaCrear,
    OTCancelar,
    OTCerrar,
    OTCrear,
    OTEditar,
    OTSalida,
    ResumenHistorial,
)
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.servicios import ordenes as servicio
from app.servicios.estado_vehiculo import actualizar_estado
from app.servicios.preventivos import recalcular, tareas_de

router = APIRouter(prefix="/ordenes-trabajo", tags=["mantenimiento"])
# Historial por vehículo (MAN-07): la spec lo sitúa en /vehiculos/{id}/historial.
router_historial = APIRouter(prefix="/vehiculos", tags=["mantenimiento"])

_422 = status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Funciones auxiliares ----------------------------------------------------


def _una(db: Db, empresa_id: int, ot_id: int) -> OTSalida:
    resultado = servicio.salidas(db, servicio.consulta_base(empresa_id).where(OrdenTrabajo.id == ot_id))
    if not resultado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden de trabajo no encontrada")
    return resultado[0]


def _ot_de_mi_empresa(db: Db, empresa_id: int, ot_id: int) -> OrdenTrabajo:
    ot = db.scalar(select(OrdenTrabajo).where(OrdenTrabajo.id == ot_id, OrdenTrabajo.empresa_id == empresa_id))
    if ot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden de trabajo no encontrada")
    return ot


def _vehiculo_bloqueado(db: Db, empresa_id: int, vehiculo_id: int) -> Vehiculo:
    """Vehículo activo de la empresa, bloqueado mientras dura la operación (422 si no vale)."""
    vehiculo = db.scalar(
        select(Vehiculo).where(Vehiculo.id == vehiculo_id, Vehiculo.empresa_id == empresa_id).with_for_update()
    )
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(_422, "El vehículo no existe o está de baja")
    return vehiculo


def _comprobar_transicion(ot: OrdenTrabajo, nuevo: EstadoOT) -> None:
    """409 si el flujo no permite el cambio. SOLO comprueba: no modifica la OT.

    El estado se cambia al final, junto con el resto de datos: si se cambiara antes,
    una consulta intermedia enviaría a la BD (autoflush) una OT "cerrada" todavía sin
    km ni fecha, y la restricción ck_orden_trabajo_cerrada_con_fecha_y_km la rechazaría.
    """
    try:
        comprobar_transicion(ot.estado, nuevo)
    except TransicionNoValida as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


def _comprobar_responsable(db: Db, empresa_id: int, persona_id: int | None) -> None:
    if persona_id is not None and not db.scalar(
        select(Persona.id).where(Persona.id == persona_id, Persona.empresa_id == empresa_id, Persona.activo)
    ):
        raise HTTPException(_422, "El responsable no existe en tu empresa o está de baja")


def _averia_tiene_otra_ot_abierta(db: Db, averia_id: int, excepto_ot: int | None = None) -> bool:
    consulta = select(OrdenTrabajo.id).where(
        OrdenTrabajo.averia_id == averia_id, OrdenTrabajo.estado.in_(ESTADOS_OT_ABIERTA)
    )
    if excepto_ot is not None:
        consulta = consulta.where(OrdenTrabajo.id != excepto_ot)
    return db.scalar(consulta) is not None


# --- Consultas ---------------------------------------------------------------


@router.get("")
def listar(
    usuario: UsuarioActual,
    db: Db,
    abiertas: bool = False,
    estado: EstadoOT | None = None,
    tipo: TipoOT | None = None,
    vehiculo_id: int | None = None,
    cerradas_desde: date | None = None,
) -> list[OTSalida]:
    """OT de la empresa, de la más reciente a la más antigua.

    ?abiertas=true: abiertas y en curso. ?cerradas_desde=AAAA-MM-DD: solo las cerradas
    desde esa fecha (p. ej. la columna "Cerradas" del tablero de taller).
    """
    consulta = servicio.consulta_base(usuario.empresa_id)
    if abiertas:
        consulta = consulta.where(OrdenTrabajo.estado.in_(ESTADOS_OT_ABIERTA))
    if estado is not None:
        consulta = consulta.where(OrdenTrabajo.estado == estado)
    if tipo is not None:
        consulta = consulta.where(OrdenTrabajo.tipo == tipo)
    if vehiculo_id is not None:
        consulta = consulta.where(OrdenTrabajo.vehiculo_id == vehiculo_id)
    if cerradas_desde is not None:
        consulta = consulta.where(OrdenTrabajo.estado == EstadoOT.CERRADA, OrdenTrabajo.fecha_cierre >= cerradas_desde)
    return servicio.salidas(db, consulta.order_by(OrdenTrabajo.abierta_en.desc(), OrdenTrabajo.id.desc()))


@router_historial.get("/{vehiculo_id}/historial")
def historial_del_vehiculo(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> HistorialSalida:
    """MAN-07: todas las OT del vehículo con fecha, tipo, km y coste (la más reciente primero),
    y el resumen de lo gastado (solo cuentan las cerradas)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    ordenes = servicio.salidas(db, servicio.consulta_base(usuario.empresa_id).where(OrdenTrabajo.vehiculo_id == vehiculo.id))
    items = sorted(
        (
            HistorialItem(
                ot_id=o.id,
                fecha=o.fecha_cierre or o.abierta_en.date(),
                tipo=o.tipo,
                estado=o.estado,
                descripcion=o.descripcion,
                km=o.km_cierre,
                coste=o.coste.total,
            )
            for o in ordenes
        ),
        key=lambda i: (i.fecha, i.ot_id),
        reverse=True,
    )
    cerradas = [o for o in ordenes if o.estado == EstadoOT.CERRADA]

    def suma(tipo: TipoOT | None = None) -> float:
        return round(sum(o.coste.total for o in cerradas if tipo is None or o.tipo == tipo), 2)

    return HistorialSalida(
        resumen=ResumenHistorial(
            ordenes=len(ordenes),
            cerradas=len(cerradas),
            coste_total=suma(),
            coste_preventivo=suma(TipoOT.PREVENTIVA),
            coste_correctivo=suma(TipoOT.CORRECTIVA),
        ),
        ordenes=items,
    )


@router.get("/{ot_id}")
def ver(ot_id: int, usuario: UsuarioActual, db: Db) -> OTSalida:
    return _una(db, usuario.empresa_id, ot_id)


# --- Crear (MAN-04) ----------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(datos: OTCrear, usuario: GestionTaller, db: Db) -> OTSalida:
    """Crea una OT desde una avería, desde un plan o a mano (ver OTCrear)."""
    eid = usuario.empresa_id
    _comprobar_responsable(db, eid, datos.responsable_id)
    averia: Averia | None = None

    if datos.averia_id is not None:
        # Desde una avería: correctiva, del vehículo de la avería, y la avería pasa a "en reparación".
        averia = db.scalar(select(Averia).where(Averia.id == datos.averia_id, Averia.empresa_id == eid))
        if averia is None:
            raise HTTPException(_422, "La avería no existe en tu empresa")
        if averia.estado == EstadoAveria.RESUELTA:
            raise HTTPException(_422, "La avería ya está resuelta")
        if _averia_tiene_otra_ot_abierta(db, averia.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Esa avería ya tiene una orden de trabajo abierta")
        if datos.vehiculo_id is not None and datos.vehiculo_id != averia.vehiculo_id:
            raise HTTPException(_422, "La avería es de otro vehículo")
        vehiculo = _vehiculo_bloqueado(db, eid, averia.vehiculo_id)
        inmovilizante = averia.gravedad == GravedadAveria.INMOVILIZA
        if inmovilizante and datos.inmoviliza is False:
            # Si no, el vehículo pasaría de "inmovilizado" a "operativo" con la avería sin reparar.
            raise HTTPException(_422, "La avería inmoviliza el vehículo: la OT también debe inmovilizarlo")
        ot = OrdenTrabajo(
            tipo=TipoOT.CORRECTIVA,
            origen=OrigenOT.AVERIA,
            averia_id=averia.id,
            inmoviliza=inmovilizante if datos.inmoviliza is None else datos.inmoviliza,
            descripcion=datos.descripcion or averia.descripcion,
        )
        averia.estado = EstadoAveria.EN_REPARACION

    elif datos.plan_id is not None:
        # Desde un plan: preventiva; el plan debe aplicarse al tipo del vehículo.
        assert datos.vehiculo_id is not None  # lo garantiza OTCrear
        vehiculo = _vehiculo_bloqueado(db, eid, datos.vehiculo_id)
        plan = db.scalar(
            select(PlanMantenimiento).where(
                PlanMantenimiento.id == datos.plan_id, PlanMantenimiento.empresa_id == eid, PlanMantenimiento.activo
            )
        )
        if plan is None or plan.tipo_vehiculo_id != vehiculo.tipo_id:
            raise HTTPException(_422, "Ese plan no existe o no se aplica a este vehículo")
        tareas = tareas_de(db, [plan.id])[plan.id]
        ot = OrdenTrabajo(
            tipo=TipoOT.PREVENTIVA,
            origen=OrigenOT.PLAN,
            plan_id=plan.id,
            inmoviliza=True if datos.inmoviliza is None else datos.inmoviliza,
            descripcion=datos.descripcion or (f"{plan.nombre}: " + "; ".join(tareas) if tareas else plan.nombre),
        )

    else:
        # A mano.
        assert datos.vehiculo_id is not None and datos.tipo is not None and datos.descripcion is not None
        vehiculo = _vehiculo_bloqueado(db, eid, datos.vehiculo_id)
        ot = OrdenTrabajo(
            tipo=datos.tipo,
            origen=OrigenOT.MANUAL,
            inmoviliza=bool(datos.inmoviliza),
            descripcion=datos.descripcion,
        )

    ot.empresa_id = eid
    ot.vehiculo_id = vehiculo.id
    ot.responsable_id = datos.responsable_id
    ot.creada_por_id = usuario.id
    db.add(ot)
    db.flush()
    actualizar_estado(db, vehiculo)  # regla 1: si inmoviliza, "en taller"
    db.commit()
    return _una(db, eid, ot.id)


# --- Editar ------------------------------------------------------------------


@router.patch("/{ot_id}")
def editar(ot_id: int, datos: OTEditar, usuario: GestionTaller, db: Db) -> OTSalida:
    """Descripción, responsable o si inmoviliza (solo con la OT abierta o en curso)."""
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    if not editable(ot.estado):
        raise HTTPException(status.HTTP_409_CONFLICT, "Una OT cerrada o cancelada no se modifica")
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("descripcion", "") is None or cambios.get("inmoviliza", True) is None:
        raise HTTPException(_422, "La descripción y 'inmoviliza' no pueden quedar vacíos")
    _comprobar_responsable(db, usuario.empresa_id, cambios.get("responsable_id"))
    if cambios.get("inmoviliza") is False and ot.averia_id is not None:
        averia = db.get(Averia, ot.averia_id)
        if averia is not None and averia.gravedad == GravedadAveria.INMOVILIZA:
            raise HTTPException(_422, "La avería inmoviliza el vehículo: la OT también debe inmovilizarlo")

    for campo, valor in cambios.items():
        setattr(ot, campo, valor)
    db.flush()
    vehiculo = _vehiculo_bloqueado(db, usuario.empresa_id, ot.vehiculo_id)
    actualizar_estado(db, vehiculo)
    db.commit()
    return _una(db, usuario.empresa_id, ot.id)


# --- Flujo (MAN-05) ----------------------------------------------------------


@router.post("/{ot_id}/iniciar")
def iniciar(ot_id: int, usuario: GestionTaller, db: Db) -> OTSalida:
    """Abierta -> en curso."""
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    _comprobar_transicion(ot, EstadoOT.EN_CURSO)
    ot.estado, ot.iniciada_en = EstadoOT.EN_CURSO, datetime.now(UTC)
    db.commit()
    return _una(db, usuario.empresa_id, ot.id)


@router.post("/{ot_id}/cerrar")
def cerrar(ot_id: int, datos: OTCerrar, usuario: GestionTaller, db: Db) -> OTSalida:
    """En curso -> cerrada. Exige km (y fecha; sin ella, hoy).

    - Los km se registran como lectura: deben encajar con el historial (FLO-05), si no 422.
    - Si viene de una avería, la avería queda resuelta.
    - Si es preventiva, el plan recalcula el próximo a partir de esta fecha y estos km.
    - El vehículo sale del taller (regla 1), salvo que tenga otras OT o averías que lo impidan.
    """
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    vehiculo = _vehiculo_bloqueado(db, usuario.empresa_id, ot.vehiculo_id)
    _comprobar_transicion(ot, EstadoOT.CERRADA)

    hoy = date.today()
    fecha = datos.fecha or hoy
    if fecha > hoy:
        raise HTTPException(_422, "La fecha de cierre no puede ser futura")
    if fecha < ot.abierta_en.date():
        raise HTTPException(_422, "La fecha de cierre no puede ser anterior a la apertura de la OT")

    # Los km de cierre, como lectura de km (regla de FLO-05).
    existentes = [Lectura(l.fecha, l.km) for l in db.scalars(select(LecturaKm).where(LecturaKm.vehiculo_id == vehiculo.id))]
    nueva = Lectura(fecha, datos.km)
    try:
        comprobar_lectura(nueva, existentes, hoy)
    except LecturaNoValida as error:
        raise HTTPException(_422, f"Km de cierre no válidos: {error}") from error
    db.add(LecturaKm(empresa_id=vehiculo.empresa_id, vehiculo_id=vehiculo.id, fecha=fecha, km=datos.km, registrada_por_id=usuario.id))
    vehiculo.km_actuales = km_actuales([*existentes, nueva])

    # Todo validado: ahora sí, la OT pasa a cerrada con su fecha y sus km (a la vez).
    ot.estado = EstadoOT.CERRADA
    ot.fecha_cierre, ot.km_cierre, ot.trabajo_realizado = fecha, datos.km, datos.trabajo_realizado

    if ot.averia_id is not None:
        averia = db.get(Averia, ot.averia_id)
        if averia is not None and averia.estado != EstadoAveria.RESUELTA:
            averia.estado = EstadoAveria.RESUELTA
            averia.resuelta_en = datetime.now(UTC)
            averia.nota_resolucion = datos.trabajo_realizado or f"Resuelta con la orden de trabajo n.º {ot.id}"

    if ot.tipo == TipoOT.PREVENTIVA and ot.plan_id is not None:
        plan = db.get(PlanMantenimiento, ot.plan_id)
        estado_plan = db.scalar(select(EstadoPlan).where(EstadoPlan.vehiculo_id == vehiculo.id, EstadoPlan.plan_id == ot.plan_id))
        if plan is not None:
            if estado_plan is None:
                estado_plan = EstadoPlan(empresa_id=vehiculo.empresa_id, vehiculo_id=vehiculo.id, plan_id=plan.id, ultima_fecha=fecha, ultimos_km=datos.km)
                db.add(estado_plan)
            estado_plan.ultima_fecha, estado_plan.ultimos_km = fecha, datos.km
            recalcular(estado_plan, plan)  # MAN-05: siguiente fecha y siguientes km

    db.flush()
    actualizar_estado(db, vehiculo)
    db.commit()
    return _una(db, usuario.empresa_id, ot.id)


@router.post("/{ot_id}/cancelar")
def cancelar(ot_id: int, datos: OTCancelar, usuario: GestionTaller, db: Db) -> OTSalida:
    """-> cancelada. Si venía de una avería, la avería vuelve a "comunicada" (sigue sin reparar)."""
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    vehiculo = _vehiculo_bloqueado(db, usuario.empresa_id, ot.vehiculo_id)
    _comprobar_transicion(ot, EstadoOT.CANCELADA)
    ot.estado = EstadoOT.CANCELADA
    ot.cancelada_en, ot.motivo_cancelacion = datetime.now(UTC), datos.motivo

    if ot.averia_id is not None and not _averia_tiene_otra_ot_abierta(db, ot.averia_id, excepto_ot=ot.id):
        averia = db.get(Averia, ot.averia_id)
        if averia is not None and averia.estado == EstadoAveria.EN_REPARACION:
            averia.estado = EstadoAveria.COMUNICADA

    db.flush()
    actualizar_estado(db, vehiculo)  # si la avería inmovilizaba, vuelve a "inmovilizado"
    db.commit()
    return _una(db, usuario.empresa_id, ot.id)


# --- Líneas de coste (MAN-06) ------------------------------------------------


@router.post("/{ot_id}/lineas", status_code=status.HTTP_201_CREATED)
def anadir_linea(ot_id: int, datos: LineaCrear, usuario: GestionTaller, db: Db) -> OTSalida:
    """Añade una línea (mano de obra, recambio o externo). Devuelve la OT con el coste actualizado."""
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    if not editable(ot.estado):
        raise HTTPException(status.HTTP_409_CONFLICT, "Una OT cerrada o cancelada no se modifica")
    db.add(LineaOT(empresa_id=usuario.empresa_id, ot_id=ot.id, **datos.model_dump()))
    db.commit()
    return _una(db, usuario.empresa_id, ot.id)


@router.delete("/{ot_id}/lineas/{linea_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_linea(ot_id: int, linea_id: int, usuario: GestionTaller, db: Db) -> Response:
    ot = _ot_de_mi_empresa(db, usuario.empresa_id, ot_id)
    if not editable(ot.estado):
        raise HTTPException(status.HTTP_409_CONFLICT, "Una OT cerrada o cancelada no se modifica")
    linea = db.scalar(select(LineaOT).where(LineaOT.id == linea_id, LineaOT.ot_id == ot.id))
    if linea is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    db.delete(linea)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
