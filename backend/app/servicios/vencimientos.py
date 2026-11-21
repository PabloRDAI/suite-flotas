"""Vencimientos de cualquier titular: vehículos (FLO-06) y personas (PER-02).

Lo usan los routers de vehículos y de personas, y el panel. Así las "mismas reglas
de colores" (PER-02) no son una copia: es el mismo código para todos.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AplicaA, TipoVencimiento, Vencimiento
from app.reglas.vencimientos import Documento, Semaforo, dias_restantes, peor, semaforo, vigentes
from app.schemas import VencimientoSalida


class TipoNoValido(ValueError):
    """El tipo de vencimiento no existe en la empresa o no corresponde al titular."""


def _columna_titular(aplica_a: AplicaA):  # type: ignore[no-untyped-def]
    return Vencimiento.vehiculo_id if aplica_a == AplicaA.VEHICULO else Vencimiento.persona_id


def documento(v: Vencimiento, t: TipoVencimiento) -> Documento:
    """Convierte una fila de la BD al formato del motor de reglas."""
    return Documento(t.id, t.nombre, v.fecha_caducidad, t.dias_aviso, t.bloquea_salida)


def vencimientos_de(db: Session, empresa_id: int, aplica_a: AplicaA, titular_id: int) -> list[tuple[Vencimiento, TipoVencimiento]]:
    """Vencimientos de un titular con su tipo, del que caduca antes al que caduca después."""
    filas = db.execute(
        select(Vencimiento, TipoVencimiento)
        .join(TipoVencimiento, TipoVencimiento.id == Vencimiento.tipo_id)
        .where(Vencimiento.empresa_id == empresa_id, _columna_titular(aplica_a) == titular_id)
        .order_by(Vencimiento.fecha_caducidad, Vencimiento.id)
    )
    return [(v, t) for v, t in filas.tuples()]


def listar(db: Session, empresa_id: int, aplica_a: AplicaA, titular_id: int, hoy: date) -> list[VencimientoSalida]:
    """Vencimientos de un titular con semáforo, días restantes y si son el vigente."""
    filas = vencimientos_de(db, empresa_id, aplica_a, titular_id)
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


def tipo_para(db: Session, empresa_id: int, tipo_id: int, aplica_a: AplicaA) -> TipoVencimiento:
    """El tipo debe existir (activo) en la empresa y ser para este titular; si no, TipoNoValido."""
    tipo = db.scalar(
        select(TipoVencimiento).where(
            TipoVencimiento.id == tipo_id, TipoVencimiento.empresa_id == empresa_id, TipoVencimiento.activo
        )
    )
    if tipo is None:
        raise TipoNoValido("El tipo de vencimiento no existe en tu empresa")
    if tipo.aplica_a != aplica_a:
        para = "personas" if tipo.aplica_a == AplicaA.PERSONA else "vehículos"
        raise TipoNoValido(f"'{tipo.nombre}' es un tipo para {para}")
    return tipo


def documentos_en_bloque(
    db: Session, empresa_id: int, aplica_a: AplicaA, titulares: Iterable[int]
) -> dict[int, list[Documento]]:
    """Documentos de MUCHOS titulares con UNA consulta (evita el problema N+1)."""
    ids = list(titulares)
    resultado: dict[int, list[Documento]] = defaultdict(list)
    if not ids:
        return resultado
    columna = _columna_titular(aplica_a)
    filas = db.execute(
        select(columna, Vencimiento, TipoVencimiento)
        .join(TipoVencimiento, TipoVencimiento.id == Vencimiento.tipo_id)
        .where(Vencimiento.empresa_id == empresa_id, columna.in_(ids))
    )
    for titular_id, v, t in filas.tuples():
        resultado[titular_id].append(documento(v, t))
    return resultado


def peor_semaforo(documentos: Iterable[Documento], hoy: date) -> Semaforo:
    """El peor semáforo de la documentación VIGENTE (verde si no tiene ninguna)."""
    return peor(semaforo(d.fecha_caducidad, d.dias_aviso, hoy) for d in vigentes(documentos))
