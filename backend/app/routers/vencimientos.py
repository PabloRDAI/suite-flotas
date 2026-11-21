"""Vencimientos de documentación de un vehículo (FLO-06) y "apto para salir" (FLO-07).

El semáforo y la aptitud los calcula app/reglas/vencimientos.py (Python puro,
con sus propios tests); este router carga los datos y llama a esas reglas.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, GestionFlota, UsuarioActual
from app.models import AplicaA, TipoVencimiento, Usuario, Vehiculo, Vencimiento
from app.reglas.vencimientos import Documento, aptitud_para_salir, dias_restantes, semaforo
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.schemas import AptitudSalida, VencimientoCrear, VencimientoSalida

router = APIRouter(prefix="/vehiculos/{vehiculo_id}", tags=["vehículos"])


def _vencimientos(db: Db, vehiculo: Vehiculo) -> list[tuple[Vencimiento, TipoVencimiento]]:
    """Vencimientos del vehículo con su tipo, del que caduca antes al que caduca después."""
    filas = db.execute(
        select(Vencimiento, TipoVencimiento)
        .join(TipoVencimiento, TipoVencimiento.id == Vencimiento.tipo_id)
        .where(Vencimiento.vehiculo_id == vehiculo.id, Vencimiento.empresa_id == vehiculo.empresa_id)
        .order_by(Vencimiento.fecha_caducidad, Vencimiento.id)
    )
    return [(v, t) for v, t in filas.tuples()]


def _documento(v: Vencimiento, t: TipoVencimiento) -> Documento:
    """Convierte una fila de la BD al formato del motor de reglas."""
    return Documento(t.id, t.nombre, v.fecha_caducidad, t.dias_aviso, t.bloquea_salida)


@router.get("/vencimientos")
def listar_vencimientos(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> list[VencimientoSalida]:
    """Documentos del vehículo con su semáforo. `vigente=false` indica que es historial (ya renovado)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    filas = _vencimientos(db, vehiculo)
    hoy = date.today()

    # Vigente = de cada tipo, el que caduca más tarde (misma regla que reglas.vigentes).
    # Las filas vienen ordenadas por fecha de caducidad: el último de cada tipo gana.
    vigente_por_tipo = {t.id: v.id for v, t in filas}

    return [
        VencimientoSalida(
            id=v.id,
            tipo_id=t.id,
            tipo_nombre=t.nombre,
            fecha_caducidad=v.fecha_caducidad,
            notas=v.notas,
            dias_restantes=dias_restantes(v.fecha_caducidad, hoy),
            semaforo=semaforo(v.fecha_caducidad, t.dias_aviso, hoy),
            vigente=vigente_por_tipo[t.id] == v.id,
        )
        for v, t in filas
    ]


@router.post("/vencimientos", status_code=status.HTTP_201_CREATED)
def registrar_vencimiento(
    vehiculo_id: int, datos: VencimientoCrear, usuario: GestionFlota, db: Db
) -> VencimientoSalida:
    """Registra un documento o la renovación de uno existente (el anterior pasa a historial).

    422 si el tipo no existe en la empresa o es un tipo para personas.
    """
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True)
    tipo = _tipo_de_vehiculo(db, usuario, datos.tipo_id)

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
    return next(v for v in listar_vencimientos(vehiculo.id, usuario, db) if v.id == vencimiento.id)


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
    documentos = [_documento(v, t) for v, t in _vencimientos(db, vehiculo)]
    resultado = aptitud_para_salir(vehiculo.activo, vehiculo.estado, documentos, date.today())
    return AptitudSalida(apto=resultado.apto, motivos=resultado.motivos, semaforo=resultado.semaforo)


def _tipo_de_vehiculo(db: Db, usuario: Usuario, tipo_id: int) -> TipoVencimiento:
    """El tipo debe existir (activo) en la empresa y ser un tipo para vehículos; si no, 422."""
    tipo = db.scalar(
        select(TipoVencimiento).where(
            TipoVencimiento.id == tipo_id,
            TipoVencimiento.empresa_id == usuario.empresa_id,
            TipoVencimiento.activo,
        )
    )
    if tipo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El tipo de vencimiento no existe en tu empresa")
    if tipo.aplica_a != AplicaA.VEHICULO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{tipo.nombre}' es un tipo para personas")
    return tipo
