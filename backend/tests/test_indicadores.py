"""Tests de los indicadores de mantenimiento (MAN-08).

Criterio: "Los valores del panel coinciden con un cálculo manual sobre los datos de
demostración". El "cálculo manual" se hace aquí por un camino INDEPENDIENTE: a partir
del plan de la demo (listas de Python), sin base de datos, sin SQL y sin el servicio,
y con otro algoritmo para los días (un conjunto de fechas en vez de unir intervalos).
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import RolUsuario
from app.reglas.ordenes import Linea, TipoOT, coste
from app.servicios.demo import (
    AVERIAS_DEMO,
    PASSWORD_DEMO,
    crear_empresa_demo,
    email_demo,
    planificar_demo,
    planificar_ordenes,
    planificar_preventivos,
)
from tests.fabricas import cabeceras, crear_empresa, crear_usuario, crear_vehiculo

HOY = date.today()
DESDE = HOY - timedelta(days=182)


def calculo_manual() -> dict[str, Any]:
    """Los indicadores de la demo calculados "a mano" desde el plan de datos."""
    vehiculos = planificar_demo(HOY)
    ordenes = planificar_ordenes(HOY, vehiculos, planificar_preventivos(HOY, vehiculos))
    cerradas = [o for o in ordenes if o.cerrada and DESDE <= o.cerrada <= HOY]

    def coste_de(o: Any) -> Decimal:
        return coste(Linea(c, q, p) for c, _, q, p in o.lineas).total

    # Días de inmovilización: un CONJUNTO de fechas por vehículo (otro algoritmo que el del servicio).
    dias: dict[int, set[date]] = {n: set() for n in range(len(vehiculos))}

    def marcar(n: int, inicio: date, fin: date) -> None:
        dia = inicio
        while dia <= fin:
            if DESDE <= dia <= HOY:
                dias[n].add(dia)
            dia += timedelta(days=1)

    for o in ordenes:
        if o.inmoviliza:
            marcar(o.vehiculo, o.abierta, o.cerrada or HOY)
    for n, gravedad, _, resuelta, hace in AVERIAS_DEMO:
        if gravedad == "inmoviliza":
            comunicada = HOY - timedelta(days=hace)
            marcar(n, comunicada, comunicada + timedelta(days=1) if resuelta else HOY)

    coste_total = sum((coste_de(o) for o in cerradas), Decimal("0.00"))
    coste_prev = sum((coste_de(o) for o in cerradas if o.tipo == TipoOT.PREVENTIVA), Decimal("0.00"))
    # Km: las lecturas de la demo empiezan justo el primer día del periodo.
    km = {n: v.lecturas[-1][1] - v.lecturas[0][1] for n, v in enumerate(vehiculos)}
    n_prev = sum(1 for o in cerradas if o.tipo == TipoOT.PREVENTIVA)
    return {
        "matriculas": {n: v.matricula for n, v in enumerate(vehiculos)},
        "coste": coste_total,
        "coste_preventivo": coste_prev,
        "ot_cerradas": len(cerradas),
        "ot_preventivas": n_prev,
        "pct_preventivo_ot": round(100 * n_prev / len(cerradas), 1),
        "pct_preventivo_coste": float((coste_prev * 100 / coste_total).quantize(Decimal("0.1"), ROUND_HALF_UP)),
        "averias": len(AVERIAS_DEMO),
        "km": km,
        "km_total": sum(km.values()),
        "coste_por_km": float((coste_total / sum(km.values())).quantize(Decimal("0.001"), ROUND_HALF_UP)),
        "dias": {n: len(d) for n, d in dias.items()},
        "coste_por_vehiculo": {
            n: sum((coste_de(o) for o in cerradas if o.vehiculo == n), Decimal("0.00")) for n in range(len(vehiculos))
        },
    }


@pytest.fixture
def demo(api: TestClient, db: Session) -> dict[str, Any]:
    crear_empresa_demo(db, hoy=HOY)
    token = api.post("/auth/login", json={"email": email_demo("admin"), "password": PASSWORD_DEMO}).json()["access_token"]
    return api.get("/panel/indicadores", headers={"Authorization": f"Bearer {token}"}).json()


# --- MAN-08: coinciden con el cálculo manual ---------------------------------


def test_los_indicadores_de_flota_coinciden_con_el_calculo_manual(demo: dict) -> None:
    """Criterio literal de MAN-08 (flota)."""
    manual = calculo_manual()
    f = demo["flota"]

    assert f["coste"] == float(manual["coste"])
    assert f["coste_preventivo"] == float(manual["coste_preventivo"])
    assert f["ot_cerradas"] == manual["ot_cerradas"]
    assert f["ot_preventivas"] == manual["ot_preventivas"]
    assert f["pct_preventivo_ot"] == manual["pct_preventivo_ot"]
    assert f["pct_preventivo_coste"] == manual["pct_preventivo_coste"]
    assert f["averias"] == manual["averias"]
    assert f["km_recorridos"] == manual["km_total"]
    assert f["coste_por_km"] == manual["coste_por_km"]
    assert f["dias_inmovilizado"] == sum(manual["dias"].values())


def test_los_indicadores_por_vehiculo_coinciden_con_el_calculo_manual(demo: dict) -> None:
    """Criterio literal de MAN-08 (por vehículo)."""
    manual = calculo_manual()
    por_matricula = {v["matricula"]: v for v in demo["vehiculos"]}

    for n, matricula in manual["matriculas"].items():
        v = por_matricula[matricula]
        assert v["coste"] == float(manual["coste_por_vehiculo"][n]), matricula
        assert v["km_recorridos"] == manual["km"][n], matricula
        assert v["dias_inmovilizado"] == manual["dias"][n], matricula


def test_valores_concretos_de_la_demo(demo: dict) -> None:
    """Algunos valores fijos de la demo (semilla fija), comprobables con una calculadora."""
    f = demo["flota"]

    assert f["coste"] == 12_535.10  # 9.748,00 € preventivo + 2.787,10 € correctivo
    assert (f["coste_preventivo"], f["coste_correctivo"]) == (9_748.00, 2_787.10)
    assert (f["ot_cerradas"], f["ot_preventivas"], f["ot_correctivas"]) == (42, 32, 10)
    assert f["pct_preventivo_ot"] == 76.2  # 32 / 42
    assert f["pct_preventivo_coste"] == 77.8  # 9.748,00 / 12.535,10
    assert f["averias"] == 4


def test_los_vehiculos_salen_de_mayor_a_menor_coste(demo: dict) -> None:
    costes = [v["coste"] for v in demo["vehiculos"]]

    assert costes == sorted(costes, reverse=True)
    assert len(costes) == 25


# --- Periodo, filtros, permisos ----------------------------------------------


@pytest.fixture
def auth_demo(api: TestClient, db: Session) -> dict[str, str]:
    crear_empresa_demo(db, hoy=HOY)
    token = api.post("/auth/login", json={"email": email_demo("trafico"), "password": PASSWORD_DEMO}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_un_periodo_sin_actividad(api: TestClient, auth_demo: dict) -> None:
    """Hace dos años no había OT ni averías: todo a cero."""
    hace_2_anos = str(HOY - timedelta(days=730))
    r = api.get("/panel/indicadores", params={"desde": hace_2_anos, "hasta": str(HOY - timedelta(days=700))}, headers=auth_demo)

    f = r.json()["flota"]
    assert (f["coste"], f["ot_cerradas"], f["averias"], f["dias_inmovilizado"]) == (0, 0, 0, 0)
    assert f["pct_preventivo_ot"] is None  # sin OT no hay porcentaje


def test_el_periodo_por_defecto_son_6_meses(api: TestClient, auth_demo: dict) -> None:
    r = api.get("/panel/indicadores", headers=auth_demo).json()

    assert (r["desde"], r["hasta"]) == (str(DESDE), str(HOY))


def test_fechas_al_reves_responden_422(api: TestClient, auth_demo: dict) -> None:
    r = api.get("/panel/indicadores", params={"desde": str(HOY), "hasta": str(HOY - timedelta(days=1))}, headers=auth_demo)

    assert r.status_code == 422


def test_filtro_por_tipo(api: TestClient, auth_demo: dict) -> None:
    tipos = api.get("/tipos-vehiculo", headers=auth_demo).json()
    cisterna = next(t["id"] for t in tipos if t["nombre"] == "Cisterna")

    r = api.get("/panel/indicadores", params={"tipo_id": cisterna}, headers=auth_demo).json()

    assert len(r["vehiculos"]) == 3  # las 3 cisternas de la demo
    assert r["flota"]["coste"] == pytest.approx(sum(v["coste"] for v in r["vehiculos"]))


def test_cada_empresa_ve_solo_sus_indicadores(api: TestClient, db: Session) -> None:
    empresa = crear_empresa(db)
    crear_vehiculo(db, empresa)
    auth = cabeceras(crear_usuario(db, empresa, "x@example.com", RolUsuario.CONDUCTOR))
    crear_empresa_demo(db, hoy=HOY)  # otra empresa con mucha actividad

    r = api.get("/panel/indicadores", headers=auth).json()

    assert len(r["vehiculos"]) == 1
    assert r["flota"]["coste"] == 0
    assert r["flota"]["coste_por_km"] is None  # sin km recorridos no hay €/km
