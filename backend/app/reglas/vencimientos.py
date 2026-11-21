"""Reglas de los vencimientos de documentación (FLO-06, FLO-07, PER-02).

Regla 2 del motor (spec): "rojo si fecha_caducidad < hoy; ámbar si quedan
≤ dias_aviso; verde en otro caso". El plazo de aviso lo configura la empresa en
cada tipo de vencimiento: aquí no hay ningún plazo legal escrito.

Cuando se renueva un documento se registra un vencimiento nuevo; los antiguos
quedan como historial. Por eso, de cada tipo solo cuenta el VIGENTE: el que
caduca más tarde.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Semaforo(StrEnum):
    VERDE = "verde"  # en regla
    AMBAR = "ambar"  # caduca pronto (dentro del plazo de aviso)
    ROJO = "rojo"  # caducado


# Orden de gravedad, para saber cuál es el peor de varios.
_GRAVEDAD = {Semaforo.VERDE: 0, Semaforo.AMBAR: 1, Semaforo.ROJO: 2}


@dataclass(frozen=True)
class Documento:
    """Un vencimiento, con los datos de su tipo que necesitan las reglas."""

    tipo_id: int
    tipo_nombre: str
    fecha_caducidad: date
    dias_aviso: int
    bloquea_salida: bool


def dias_restantes(fecha_caducidad: date, hoy: date) -> int:
    """Días que faltan para la caducidad (negativo si ya caducó, 0 si caduca hoy)."""
    return (fecha_caducidad - hoy).days


def semaforo(fecha_caducidad: date, dias_aviso: int, hoy: date) -> Semaforo:
    """Regla 2 del motor. Un documento que caduca HOY todavía es válido hoy: ámbar."""
    if fecha_caducidad < hoy:
        return Semaforo.ROJO
    if dias_restantes(fecha_caducidad, hoy) <= dias_aviso:
        return Semaforo.AMBAR
    return Semaforo.VERDE


def peor(semaforos: Iterable[Semaforo]) -> Semaforo:
    """El más grave de varios semáforos (verde si no hay ninguno)."""
    return max(semaforos, key=_GRAVEDAD.__getitem__, default=Semaforo.VERDE)


def vigentes(documentos: Iterable[Documento]) -> list[Documento]:
    """De cada tipo, solo el documento que caduca más tarde (los demás son historial)."""
    por_tipo: dict[int, Documento] = {}
    for doc in documentos:
        actual = por_tipo.get(doc.tipo_id)
        if actual is None or doc.fecha_caducidad > actual.fecha_caducidad:
            por_tipo[doc.tipo_id] = doc
    return sorted(por_tipo.values(), key=lambda d: d.fecha_caducidad)


@dataclass(frozen=True)
class Aptitud:
    apto: bool
    motivos: list[str]  # por qué no es apto (vacía si lo es)
    semaforo: Semaforo  # el peor semáforo de su documentación vigente


def aptitud_para_salir(activo: bool, estado: str, documentos: Iterable[Documento], hoy: date) -> Aptitud:
    """FLO-07: ¿puede salir el vehículo hoy?

    No es apto si está de baja, si su estado no es "operativo", o si algún
    documento VIGENTE de un tipo que bloquea la salida está caducado (rojo).
    Un documento en ámbar avisa, pero no impide salir.
    """
    docs = vigentes(documentos)
    motivos: list[str] = []
    if not activo:
        motivos.append("El vehículo está dado de baja")
    elif estado != "operativo":
        motivos.append(f"Estado: {estado.replace('_', ' ')}")
    for doc in docs:
        if doc.bloquea_salida and semaforo(doc.fecha_caducidad, doc.dias_aviso, hoy) == Semaforo.ROJO:
            # Redacción neutra ("Seguro: caducó…", "ITV: caducó…"): vale para cualquier nombre de tipo.
            motivos.append(f"{doc.tipo_nombre}: caducó el {doc.fecha_caducidad.strftime('%d/%m/%Y')}")

    return Aptitud(
        apto=not motivos,
        motivos=motivos,
        semaforo=peor(semaforo(d.fecha_caducidad, d.dias_aviso, hoy) for d in docs),
    )
