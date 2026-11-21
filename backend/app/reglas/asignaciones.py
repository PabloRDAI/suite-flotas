"""Reglas de las asignaciones conductor-vehículo (PER-03, PER-04).

PER-03: "Un vehículo tiene como máximo un conductor habitual a la vez; el
historial de asignaciones se conserva."
PER-04: "Si se asigna un conductor con el permiso o el CAP vencidos, el sistema
avisa (sin bloquear)."

Una asignación ocupa el periodo [desde, hasta], ambos días incluidos. Si "hasta"
está vacío, sigue vigente (hasta nuevo aviso).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.reglas.vencimientos import Documento, Semaforo, semaforo, vigentes


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date | None  # None = sin fecha de fin

    def contiene(self, dia: date) -> bool:
        return self.desde <= dia and (self.hasta is None or dia <= self.hasta)


def se_solapan(a: Periodo, b: Periodo) -> bool:
    """¿Comparten algún día? (Un periodo sin fin llega hasta el infinito.)"""
    a_termina_antes = a.hasta is not None and a.hasta < b.desde
    b_termina_antes = b.hasta is not None and b.hasta < a.desde
    return not (a_termina_antes or b_termina_antes)


@dataclass(frozen=True)
class AsignacionExistente:
    persona: str  # nombre, para el mensaje
    periodo: Periodo
    habitual: bool


class AsignacionNoValida(ValueError):
    """La asignación incumple una regla que SÍ bloquea (PER-03)."""


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def comprobar_habitual(nuevo: Periodo, habitual: bool, existentes: Iterable[AsignacionExistente]) -> None:
    """PER-03: lanza AsignacionNoValida si la nueva asignación HABITUAL se solapa con otra habitual.

    Las temporales (sustituciones, refuerzos) pueden coincidir con cualquier otra.
    """
    if not habitual:
        return
    for otra in existentes:
        if otra.habitual and se_solapan(nuevo, otra.periodo):
            hasta = f" hasta el {_fmt(otra.periodo.hasta)}" if otra.periodo.hasta else ""
            raise AsignacionNoValida(
                f"El vehículo ya tiene como conductor/a habitual a {otra.persona} "
                f"desde el {_fmt(otra.periodo.desde)}{hasta}. Finaliza esa asignación antes."
            )


def avisos_de_documentacion(documentos: Iterable[Documento], dia: date) -> list[str]:
    """PER-04: avisos (que NO bloquean) por documentación de la persona caducada ese día.

    No se escriben aquí nombres de documentos ("CAP", "permiso"…): cuenta cualquier
    documento vigente de un tipo que la empresa marcó como imprescindible (bloquea_salida).
    """
    return [
        f"{d.tipo_nombre}: caducó el {_fmt(d.fecha_caducidad)}"
        for d in vigentes(documentos)
        if d.bloquea_salida and semaforo(d.fecha_caducidad, d.dias_aviso, dia) == Semaforo.ROJO
    ]
