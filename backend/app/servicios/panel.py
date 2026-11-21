"""Panel de flota (FLO-04): contadores, tabla de vehículos con su aptitud y alertas.

Rendimiento ("carga en menos de 1 s con 150 vehículos"): todo sale de DOS
consultas (los vehículos y todos sus vencimientos de una vez) y las reglas se
aplican en memoria. Pedir la aptitud vehículo a vehículo serían 150 consultas.

Coherencia ("totales que coinciden con el listado filtrado"): contadores,
tabla y alertas se calculan sobre la misma lista de vehículos.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoVehiculo, TipoVencimiento, Vehiculo, Vencimiento
from app.reglas.vencimientos import Documento, Semaforo, aptitud_para_salir, dias_restantes, semaforo, vigentes
from app.schemas import AlertaPanel, ContadoresPanel, PanelSalida, VehiculoPanel

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
    documentos: dict[int, list[Documento]] = defaultdict(list)
    if vehiculos:
        filas = db.execute(
            select(Vencimiento.vehiculo_id, Vencimiento.fecha_caducidad, TipoVencimiento)
            .join(TipoVencimiento, TipoVencimiento.id == Vencimiento.tipo_id)
            .where(Vencimiento.empresa_id == empresa_id, Vencimiento.vehiculo_id.in_([v.id for v in vehiculos]))
        )
        for vehiculo_id, caduca, t in filas.tuples():
            documentos[vehiculo_id].append(Documento(t.id, t.nombre, caduca, t.dias_aviso, t.bloquea_salida))

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

    # Lo más urgente primero: rojos, luego ámbar; dentro de cada color, lo que antes caduca.
    alertas.sort(key=lambda a: (_ORDEN_URGENCIA[a.semaforo], a.dias_restantes, a.matricula))

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
