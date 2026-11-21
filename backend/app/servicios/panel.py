"""Panel de flota (FLO-04): contadores, tabla de vehículos con su aptitud y alertas.

Rendimiento ("carga en menos de 1 s con 150 vehículos"): todo sale de DOS
consultas (los vehículos y todos sus vencimientos de una vez) y las reglas se
aplican en memoria. Pedir la aptitud vehículo a vehículo serían 150 consultas.

Alertas: averías abiertas (MAN-03), documentación caducada o a punto de caducar
(FLO-06) y preventivos vencidos o próximos (MAN-02).

Coherencia ("totales que coinciden con el listado filtrado"): contadores,
tabla y alertas se calculan sobre la misma lista de vehículos.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AplicaA, Averia, EstadoVehiculo, Vehiculo
from app.reglas.estado_vehiculo import EstadoAveria, GravedadAveria
from app.reglas.vencimientos import Semaforo, aptitud_para_salir, dias_restantes, semaforo, vigentes
from app.schemas import AlertaPanel, ContadoresPanel, PanelSalida, VehiculoPanel
from app.reglas.preventivo import Situacion
from app.servicios.preventivos import prevision
from app.servicios.vencimientos import documentos_en_bloque

_ORDEN_URGENCIA = {Semaforo.ROJO: 0, Semaforo.AMBAR: 1, Semaforo.VERDE: 2}


def _mensaje_vencimiento(nombre: str, dias: int) -> str:
    """Redacción neutra ("Seguro: caducó…", "ITV: caducó…"): los nombres los pone cada empresa
    y no sabemos su género, así que se evita concordar ("caducado/caducada")."""
    if dias < 0:
        return f"{nombre}: caducó hace {-dias} día{'s' if dias != -1 else ''}"
    if dias == 0:
        return f"{nombre}: caduca hoy"
    return f"{nombre}: caduca en {dias} día{'s' if dias != 1 else ''}"


def calcular_panel(
    db: Session, empresa_id: int, hoy: date, centro_id: int | None = None, tipo_id: int | None = None
) -> PanelSalida:
    """Panel de los vehículos ACTIVOS de la empresa, con filtros opcionales por centro y tipo."""
    # Consulta 1: los vehículos (filtrados).
    consulta = select(Vehiculo).where(Vehiculo.empresa_id == empresa_id, Vehiculo.activo)
    if centro_id is not None:
        consulta = consulta.where(Vehiculo.centro_id == centro_id)
    if tipo_id is not None:
        consulta = consulta.where(Vehiculo.tipo_id == tipo_id)
    vehiculos = list(db.scalars(consulta.order_by(Vehiculo.matricula)))

    # Consulta 2: TODOS los vencimientos de esos vehículos, con su tipo, de una vez.
    documentos = documentos_en_bloque(db, empresa_id, AplicaA.VEHICULO, (v.id for v in vehiculos))

    # El resto, en memoria con las reglas del motor.
    filas_panel: list[VehiculoPanel] = []
    alertas: list[AlertaPanel] = []
    for v in vehiculos:
        aptitud = aptitud_para_salir(v.activo, v.estado, documentos[v.id], hoy)
        filas_panel.append(
            VehiculoPanel(
                id=v.id,
                matricula=v.matricula,
                marca=v.marca,
                modelo=v.modelo,
                tipo_id=v.tipo_id,
                centro_id=v.centro_id,
                km_actuales=v.km_actuales,
                estado=v.estado,
                apto=aptitud.apto,
                motivos=aptitud.motivos,
                semaforo=aptitud.semaforo,
            )
        )
        for doc in vigentes(documentos[v.id]):
            color = semaforo(doc.fecha_caducidad, doc.dias_aviso, hoy)
            if color != Semaforo.VERDE:
                dias = dias_restantes(doc.fecha_caducidad, hoy)
                alertas.append(
                    AlertaPanel(
                        tipo="vencimiento",
                        semaforo=color,
                        vehiculo_id=v.id,
                        matricula=v.matricula,
                        mensaje=_mensaje_vencimiento(doc.tipo_nombre, dias),
                        fecha=doc.fecha_caducidad,
                        dias_restantes=dias,
                    )
                )

    # Preventivos vencidos (rojo) y próximos (ámbar) de esos mismos vehículos (MAN-02).
    # La previsión ya viene ordenada por urgencia; se conserva ese orden dentro de cada color.
    for p in prevision(db, empresa_id, hoy, vehiculo_ids=[v.id for v in vehiculos]):
        alertas.append(
            AlertaPanel(
                tipo="preventivo",
                semaforo=Semaforo.ROJO if p.situacion == Situacion.VENCIDO else Semaforo.AMBAR,
                vehiculo_id=p.vehiculo_id,
                matricula=p.matricula,
                mensaje=f"{p.plan_nombre}: {p.motivo}",
                fecha=p.proxima_fecha,
                dias_restantes=p.dias_restantes,
            )
        )

    # Averías abiertas (MAN-03): las que inmovilizan en rojo; graves y leves en ámbar.
    if vehiculos:
        matricula = {v.id: v.matricula for v in vehiculos}
        abiertas = db.scalars(
            select(Averia)
            .where(Averia.vehiculo_id.in_(matricula), Averia.estado != EstadoAveria.RESUELTA)
            .order_by(Averia.comunicada_en)
        )
        for a in abiertas:
            descripcion = a.descripcion if len(a.descripcion) <= 60 else a.descripcion[:57] + "…"
            alertas.append(
                AlertaPanel(
                    tipo="averia",
                    semaforo=Semaforo.ROJO if a.gravedad == GravedadAveria.INMOVILIZA else Semaforo.AMBAR,
                    vehiculo_id=a.vehiculo_id,
                    matricula=matricula[a.vehiculo_id],
                    mensaje=f"Avería ({a.gravedad.replace('_', ' ')}): {descripcion}",
                    fecha=a.comunicada_en.date(),
                    dias_restantes=None,
                )
            )

    # Lo más urgente primero: rojos, luego ámbar. Dentro de cada color: averías (un vehículo
    # parado o con un problema), documentación (por fecha) y preventivos (en su orden de urgencia).
    orden_tipo = {"averia": 0, "vencimiento": 1, "preventivo": 2}

    def clave(a: AlertaPanel) -> tuple[int, int, int, str]:
        por_fecha = a.tipo == "vencimiento"
        return (
            _ORDEN_URGENCIA[a.semaforo],
            orden_tipo[a.tipo],
            (a.dias_restantes or 0) if por_fecha else 0,
            a.matricula if por_fecha else "",
        )

    alertas.sort(key=clave)  # sort es estable: averías y preventivos conservan su orden

    def contar(estado: EstadoVehiculo) -> int:
        return sum(1 for f in filas_panel if f.estado == estado)

    aptos = sum(1 for f in filas_panel if f.apto)
    return PanelSalida(
        fecha=hoy,
        contadores=ContadoresPanel(
            total=len(filas_panel),
            operativo=contar(EstadoVehiculo.OPERATIVO),
            en_taller=contar(EstadoVehiculo.EN_TALLER),
            inmovilizado=contar(EstadoVehiculo.INMOVILIZADO),
            aptos=aptos,
            no_aptos=len(filas_panel) - aptos,
        ),
        vehiculos=filas_panel,
        alertas=alertas,
    )
