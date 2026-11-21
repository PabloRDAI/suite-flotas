"""Asignaciones con sus avisos (PER-03, PER-04), listas para devolver por la API."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AplicaA, Asignacion, Persona, Vehiculo
from app.reglas.asignaciones import Periodo, avisos_de_documentacion
from app.schemas import AsignacionSalida
from app.servicios.vencimientos import documentos_en_bloque


def listar(
    db: Session, empresa_id: int, hoy: date, *, vehiculo_id: int | None = None, persona_id: int | None = None
) -> list[AsignacionSalida]:
    """Historial de asignaciones (de la más reciente a la más antigua) con sus avisos.

    Tres consultas en total, se listen las que se listen (sin problema N+1).
    """
    consulta = (
        select(Asignacion, Persona.nombre, Vehiculo.matricula)
        .join(Persona, Persona.id == Asignacion.persona_id)
        .join(Vehiculo, Vehiculo.id == Asignacion.vehiculo_id)
        .where(Asignacion.empresa_id == empresa_id)
        .order_by(Asignacion.desde.desc(), Asignacion.id.desc())
    )
    if vehiculo_id is not None:
        consulta = consulta.where(Asignacion.vehiculo_id == vehiculo_id)
    if persona_id is not None:
        consulta = consulta.where(Asignacion.persona_id == persona_id)
    filas = db.execute(consulta).tuples().all()

    documentos = documentos_en_bloque(db, empresa_id, AplicaA.PERSONA, {a.persona_id for a, _, _ in filas})
    return [salida(a, nombre, matricula, documentos[a.persona_id], hoy) for a, nombre, matricula in filas]


def salida(a: Asignacion, persona_nombre: str, matricula: str, documentos: list, hoy: date) -> AsignacionSalida:
    periodo = Periodo(a.desde, a.hasta)
    terminada = a.hasta is not None and a.hasta < hoy
    # Avisos solo de lo que está en vigor o por venir, comprobados el día en que
    # rige (hoy, o el día de inicio si empieza en el futuro). El historial no avisa.
    avisos = [] if terminada else avisos_de_documentacion(documentos, max(a.desde, hoy))
    return AsignacionSalida(
        id=a.id,
        persona_id=a.persona_id,
        persona_nombre=persona_nombre,
        vehiculo_id=a.vehiculo_id,
        matricula=matricula,
        desde=a.desde,
        hasta=a.hasta,
        habitual=a.habitual,
        notas=a.notas,
        vigente=periodo.contiene(hoy),
        avisos=avisos,
    )
