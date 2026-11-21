"""Vencimientos de documentación de un vehículo (FLO-06) y "apto para salir" (FLO-07).

La lógica común con las personas está en app/servicios/vencimientos.py y las
reglas (semáforo, vigentes, aptitud) en app/reglas/vencimientos.py.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, GestionFlota, UsuarioActual
from app.models import AplicaA, Vencimiento
from app.reglas.vencimientos import aptitud_para_salir
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.schemas import AptitudSalida, VencimientoCrear, VencimientoSalida
from app.servicios import vencimientos as servicio

router = APIRouter(prefix="/vehiculos/{vehiculo_id}", tags=["vehículos"])


@router.get("/vencimientos")
def listar_vencimientos(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> list[VencimientoSalida]:
    """Documentos del vehículo con su semáforo. `vigente=false` indica que es historial (ya renovado)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    return servicio.listar(db, usuario.empresa_id, AplicaA.VEHICULO, vehiculo.id, date.today())


@router.post("/vencimientos", status_code=status.HTTP_201_CREATED)
def registrar_vencimiento(
    vehiculo_id: int, datos: VencimientoCrear, usuario: GestionFlota, db: Db
) -> VencimientoSalida:
    """Registra un documento o la renovación de uno existente (el anterior pasa a historial).

    422 si el tipo no existe en la empresa o es un tipo para personas.
    """
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    try:
        tipo = servicio.tipo_para(db, usuario.empresa_id, datos.tipo_id, AplicaA.VEHICULO)
    except servicio.TipoNoValido as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    vencimiento = Vencimiento(
        empresa_id=usuario.empresa_id,
        vehiculo_id=vehiculo.id,
        tipo_id=tipo.id,
        fecha_caducidad=datos.fecha_caducidad,
        notas=datos.notas,
        registrado_por_id=usuario.id,
    )
    db.add(vencimiento)
    db.commit()
    lista = servicio.listar(db, usuario.empresa_id, AplicaA.VEHICULO, vehiculo.id, date.today())
    return next(v for v in lista if v.id == vencimiento.id)


@router.delete("/vencimientos/{vencimiento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_vencimiento(vehiculo_id: int, vencimiento_id: int, usuario: GestionFlota, db: Db) -> Response:
    """Borra un vencimiento registrado por error (admin y tráfico)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    vencimiento = db.scalar(
        select(Vencimiento).where(
            Vencimiento.id == vencimiento_id,
            Vencimiento.vehiculo_id == vehiculo.id,
            Vencimiento.empresa_id == usuario.empresa_id,
        )
    )
    if vencimiento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vencimiento no encontrado")
    db.delete(vencimiento)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/aptitud")
def aptitud(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> AptitudSalida:
    """FLO-07: ¿puede salir hoy? No, si no está operativo o tiene documentación vencida que bloquea."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    documentos = [
        servicio.documento(v, t)
        for v, t in servicio.vencimientos_de(db, usuario.empresa_id, AplicaA.VEHICULO, vehiculo.id)
    ]
    resultado = aptitud_para_salir(vehiculo.activo, vehiculo.estado, documentos, date.today())
    return AptitudSalida(apto=resultado.apto, motivos=resultado.motivos, semaforo=resultado.semaforo)
