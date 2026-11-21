"""Motor del próximo mantenimiento preventivo (regla 3 de la spec, MAN-01).

    proxima_fecha = ultima_fecha + intervalo_dias
    proximos_km   = ultimos_km   + intervalo_km
    Vence cuando se alcanza LA PRIMERA de las dos.

Un plan puede tener solo intervalo por km, solo por días, o los dos ("lo que
llegue antes"). Si le falta uno, esa condición simplemente no existe.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

# Previsión de MAN-02: "lo que toca en los próximos 30 días o 2.000 km".
MARGEN_DIAS = 30
MARGEN_KM = 2000


class PlanSinIntervalo(ValueError):
    """Un plan necesita al menos un intervalo (km o días)."""


@dataclass(frozen=True)
class Proximo:
    fecha: date | None  # None si el plan no tiene intervalo por días
    km: int | None  # None si el plan no tiene intervalo por km


def calcular_proximo(
    ultima_fecha: date, ultimos_km: int, intervalo_dias: int | None, intervalo_km: int | None
) -> Proximo:
    """Regla 3: cuándo toca el siguiente, por fecha y por km."""
    if not intervalo_dias and not intervalo_km:
        raise PlanSinIntervalo("El plan necesita un intervalo por km, por días o ambos")
    return Proximo(
        fecha=ultima_fecha + timedelta(days=intervalo_dias) if intervalo_dias else None,
        km=ultimos_km + intervalo_km if intervalo_km else None,
    )


class Situacion(StrEnum):
    AL_DIA = "al_dia"
    PROXIMO = "proximo"  # dentro del margen de previsión (MAN-02)
    VENCIDO = "vencido"  # se ha alcanzado la fecha o los km


@dataclass(frozen=True)
class EstadoPreventivo:
    situacion: Situacion
    vencido_por_fecha: bool
    vencido_por_km: bool
    dias_restantes: int | None  # negativo si ya pasó la fecha
    km_restantes: int | None  # negativo si ya se pasaron los km
    motivo: str  # explicación para el usuario


def _km(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def evaluar(
    proximo: Proximo,
    hoy: date,
    km_actuales: int,
    margen_dias: int = MARGEN_DIAS,
    margen_km: int = MARGEN_KM,
) -> EstadoPreventivo:
    """¿Toca ya? Vencido si se ha alcanzado la fecha O los km (lo que llegue antes).

    "Próximo" si falta poco por cualquiera de los dos (margen de MAN-02).
    """
    dias = (proximo.fecha - hoy).days if proximo.fecha else None
    km = proximo.km - km_actuales if proximo.km is not None else None
    por_fecha = dias is not None and dias <= 0
    por_km = km is not None and km <= 0

    if por_fecha and por_km:
        motivo = "Vencido por fecha y por km"
    elif por_fecha:
        motivo = f"Vencido por fecha (hace {-dias} días)" if dias else "Vence hoy"
    elif por_km:
        motivo = f"Vencido por km (se pasó en {_km(-km)} km)" if km else "Vence por km justo ahora"
    else:
        partes = []
        if dias is not None:
            partes.append(f"{dias} días")
        if km is not None:
            partes.append(f"{_km(km)} km")
        motivo = "Faltan " + " o ".join(partes)

    if por_fecha or por_km:
        situacion = Situacion.VENCIDO
    elif (dias is not None and dias <= margen_dias) or (km is not None and km <= margen_km):
        situacion = Situacion.PROXIMO
    else:
        situacion = Situacion.AL_DIA

    return EstadoPreventivo(situacion, por_fecha, por_km, dias, km, motivo)


def urgencia(estado: EstadoPreventivo, margen_dias: int = MARGEN_DIAS, margen_km: int = MARGEN_KM) -> float:
    """Índice de urgencia para ordenar la previsión (MAN-02). Cuanto MENOR, más urgente.

    Días y km no se pueden comparar directamente, así que cada uno se mide como
    la fracción del margen de previsión que queda (30 días, 2.000 km) y se toma
    la condición que llegue antes:
        1     -> justo en el borde de la previsión
        0     -> toca hoy / ahora
        < 0   -> vencido (cuanto más negativo, más atrasado)
    Ejemplo: "se pasó en 1.500 km" = -0,75 va antes que "vencido hace 15 días" = -0,5.
    """
    fracciones = []
    if estado.dias_restantes is not None:
        fracciones.append(estado.dias_restantes / margen_dias)
    if estado.km_restantes is not None:
        fracciones.append(estado.km_restantes / margen_km)
    return min(fracciones)
