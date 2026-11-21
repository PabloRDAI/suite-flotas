"""Tests unitarios del motor del próximo preventivo (regla 3, MAN-01). Sin base de datos.

Criterio de MAN-01: "Un plan 'cada 30.000 km o 12 meses' genera un aviso cuando se
cumple la primera de las dos condiciones (test unitario con ambos casos)."
"""

from datetime import date

import pytest

from app.reglas.preventivo import (
    EstadoPreventivo,
    PlanSinIntervalo,
    Proximo,
    Situacion,
    calcular_proximo,
    evaluar,
    urgencia,
)

ULTIMA = date(2026, 1, 15)
ULTIMOS_KM = 100_000

# El plan del criterio de aceptación: cada 30.000 km o 12 meses (365 días).
PLAN_30000_O_12_MESES = calcular_proximo(ULTIMA, ULTIMOS_KM, intervalo_dias=365, intervalo_km=30_000)


# --- Regla 3: cálculo del próximo --------------------------------------------


def test_calcula_la_proxima_fecha_y_los_proximos_km() -> None:
    assert PLAN_30000_O_12_MESES == Proximo(fecha=date(2027, 1, 15), km=130_000)


def test_un_plan_solo_por_km_no_tiene_fecha() -> None:
    assert calcular_proximo(ULTIMA, ULTIMOS_KM, None, 60_000) == Proximo(fecha=None, km=160_000)


def test_un_plan_solo_por_tiempo_no_tiene_km() -> None:
    assert calcular_proximo(ULTIMA, ULTIMOS_KM, 180, None) == Proximo(fecha=date(2026, 7, 14), km=None)


def test_un_plan_sin_ningun_intervalo_no_vale() -> None:
    with pytest.raises(PlanSinIntervalo):
        calcular_proximo(ULTIMA, ULTIMOS_KM, None, None)


# --- MAN-01: "lo que llegue antes" (los dos casos del criterio) ---------------


def test_vence_por_km_aunque_no_haya_llegado_la_fecha() -> None:
    """Caso 1 del criterio: 30.000 km recorridos en solo 8 meses."""
    estado = evaluar(PLAN_30000_O_12_MESES, hoy=date(2026, 9, 15), km_actuales=131_200)

    assert estado.situacion == Situacion.VENCIDO
    assert (estado.vencido_por_km, estado.vencido_por_fecha) == (True, False)
    assert estado.motivo == "Vencido por km (se pasó en 1.200 km)"


def test_vence_por_fecha_aunque_no_se_hayan_hecho_los_km() -> None:
    """Caso 2 del criterio: pasan 12 meses con solo 18.000 km."""
    estado = evaluar(PLAN_30000_O_12_MESES, hoy=date(2027, 1, 20), km_actuales=118_000)

    assert estado.situacion == Situacion.VENCIDO
    assert (estado.vencido_por_fecha, estado.vencido_por_km) == (True, False)
    assert estado.motivo == "Vencido por fecha (hace 5 días)"


def test_vencido_por_las_dos_condiciones() -> None:
    estado = evaluar(PLAN_30000_O_12_MESES, hoy=date(2027, 2, 1), km_actuales=140_000)

    assert estado.vencido_por_fecha and estado.vencido_por_km
    assert estado.motivo == "Vencido por fecha y por km"


def test_no_vence_mientras_no_se_cumpla_ninguna() -> None:
    estado = evaluar(PLAN_30000_O_12_MESES, hoy=date(2026, 6, 1), km_actuales=110_000)

    assert estado.situacion == Situacion.AL_DIA
    assert estado.dias_restantes == 228
    assert estado.km_restantes == 20_000
    assert estado.motivo == "Faltan 228 días o 20.000 km"


# --- Límites exactos ---------------------------------------------------------


@pytest.mark.parametrize(
    ("hoy", "km", "situacion"),
    [
        (date(2027, 1, 14), 100_000, Situacion.PROXIMO),  # falta 1 día: dentro del margen de 30
        (date(2027, 1, 15), 100_000, Situacion.VENCIDO),  # el mismo día: ya toca
        (date(2026, 6, 1), 129_999, Situacion.PROXIMO),  # falta 1 km: dentro del margen de 2.000
        (date(2026, 6, 1), 130_000, Situacion.VENCIDO),  # justo los km: ya toca
    ],
)
def test_limites(hoy: date, km: int, situacion: Situacion) -> None:
    assert evaluar(PLAN_30000_O_12_MESES, hoy=hoy, km_actuales=km).situacion == situacion


# --- Previsión (margen de MAN-02: 30 días o 2.000 km) ------------------------


@pytest.mark.parametrize(
    ("hoy", "km", "situacion"),
    [
        (date(2026, 12, 16), 110_000, Situacion.PROXIMO),  # faltan 30 días
        (date(2026, 12, 15), 110_000, Situacion.AL_DIA),  # faltan 31 días y 20.000 km
        (date(2026, 6, 1), 128_000, Situacion.PROXIMO),  # faltan 2.000 km
        (date(2026, 6, 1), 127_999, Situacion.AL_DIA),  # faltan 2.001 km y muchos días
    ],
)
def test_proximo_si_falta_poco_por_cualquiera_de_las_dos(hoy: date, km: int, situacion: Situacion) -> None:
    assert evaluar(PLAN_30000_O_12_MESES, hoy=hoy, km_actuales=km).situacion == situacion


def test_un_plan_solo_por_km_ignora_la_fecha() -> None:
    solo_km = calcular_proximo(ULTIMA, ULTIMOS_KM, None, 60_000)

    estado = evaluar(solo_km, hoy=date(2030, 1, 1), km_actuales=150_000)  # años después, pero sin los km

    assert estado.situacion == Situacion.AL_DIA
    assert estado.dias_restantes is None
    assert estado.motivo == "Faltan 10.000 km"


# --- MAN-02: índice de urgencia ----------------------------------------------


def estado_con(dias: int | None = None, km: int | None = None) -> EstadoPreventivo:
    """Estado con los restantes indicados (el resto de campos no influye en la urgencia)."""
    return EstadoPreventivo(Situacion.PROXIMO, False, False, dias, km, "")


@pytest.mark.parametrize(
    ("dias", "km", "esperado"),
    [
        (30, None, 1.0),  # en el borde de la previsión por fecha
        (None, 2_000, 1.0),  # en el borde por km
        (0, None, 0.0),  # toca hoy
        (12, None, 0.4),
        (None, 1_200, 0.6),
        (-15, None, -0.5),  # vencido hace 15 días
        (None, -1_500, -0.75),  # se pasó en 1.500 km
        (12, 20_000, 0.4),  # con las dos, manda la que llega antes (la fecha)
        (300, 1_200, 0.6),  # …o los km
    ],
)
def test_indice_de_urgencia(dias: int | None, km: int | None, esperado: float) -> None:
    assert urgencia(estado_con(dias, km)) == pytest.approx(esperado)


def test_ordenar_por_urgencia_mezcla_km_y_dias_con_sentido() -> None:
    """Los cuatro casos de la demo, en el orden que debe salir la previsión."""
    casos = {
        "faltan 1.200 km": estado_con(km=1_200),
        "vencido hace 15 días": estado_con(dias=-15),
        "faltan 12 días": estado_con(dias=12),
        "se pasó en 1.500 km": estado_con(km=-1_500),
    }

    orden = sorted(casos, key=lambda nombre: urgencia(casos[nombre]))

    assert orden == ["se pasó en 1.500 km", "vencido hace 15 días", "faltan 12 días", "faltan 1.200 km"]


def test_un_plan_solo_por_tiempo_ignora_los_km() -> None:
    solo_tiempo = calcular_proximo(ULTIMA, ULTIMOS_KM, 180, None)

    estado = evaluar(solo_tiempo, hoy=date(2026, 7, 14), km_actuales=999_999)

    assert estado.situacion == Situacion.VENCIDO
    assert estado.km_restantes is None
    assert estado.motivo == "Vence hoy"
