"""Tests de la previsión de preventivos (MAN-02) y de sus alertas en el panel.

Criterio: "La lista se ordena por urgencia y coincide con los cálculos del motor en los tests."
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoPlan, PlanMantenimiento, RolUsuario, Vehiculo
from app.reglas.preventivo import Situacion, calcular_proximo, evaluar, urgencia
from app.servicios.demo import PASSWORD_DEMO, crear_empresa_demo, email_demo
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, nuevo_vehiculo

HOY = date.today()


def login_demo(api: TestClient) -> dict[str, str]:
    r = api.post("/auth/login", json={"email": email_demo("taller"), "password": PASSWORD_DEMO})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def calculo_del_motor(db: Session, empresa_id: int) -> list[tuple[str, str]]:
    """La previsión calculada DIRECTAMENTE con el motor de reglas, sin pasar por la API."""
    filas = db.execute(
        select(EstadoPlan, PlanMantenimiento, Vehiculo)
        .join(PlanMantenimiento, PlanMantenimiento.id == EstadoPlan.plan_id)
        .join(Vehiculo, Vehiculo.id == EstadoPlan.vehiculo_id)
        .where(Vehiculo.empresa_id == empresa_id, Vehiculo.activo, PlanMantenimiento.activo)
    ).tuples()
    pendientes = []
    for estado, plan, vehiculo in filas:
        e = evaluar(
            calcular_proximo(estado.ultima_fecha, estado.ultimos_km, plan.intervalo_dias, plan.intervalo_km),
            HOY,
            vehiculo.km_actuales,
        )
        if e.situacion != Situacion.AL_DIA:
            pendientes.append((urgencia(e), vehiculo.matricula, plan.nombre))
    return [(matricula, plan) for _, matricula, plan in sorted(pendientes)]


# --- Criterio de aceptación de MAN-02 ----------------------------------------


def test_la_prevision_coincide_con_los_calculos_del_motor(api: TestClient, db: Session) -> None:
    """Criterio literal de MAN-02, sobre los datos de la empresa demo."""
    r = crear_empresa_demo(db, hoy=HOY)

    prevision = api.get("/preventivos/prevision", headers=login_demo(api)).json()

    assert [(p["matricula"], p["plan_nombre"]) for p in prevision] == calculo_del_motor(db, r.empresa_id)


def test_la_prevision_se_ordena_por_urgencia(api: TestClient, db: Session) -> None:
    """Los 4 casos de la demo, en orden: vencido por km, vencido por fecha, 12 días, 1.200 km."""
    crear_empresa_demo(db, hoy=HOY)

    prevision = api.get("/preventivos/prevision", headers=login_demo(api)).json()

    assert [p["situacion"] for p in prevision] == ["vencido", "vencido", "proximo", "proximo"]
    assert [p["urgencia"] for p in prevision] == sorted(p["urgencia"] for p in prevision)
    assert prevision[0]["motivo"].startswith("Vencido por km")
    assert prevision[1]["motivo"].startswith("Vencido por fecha")
    assert prevision[2]["dias_restantes"] == 12
    assert prevision[3]["km_restantes"] == 1_200
    assert prevision[0]["tareas"]  # incluye las tareas del plan, para el taller


# --- Qué entra en la previsión -----------------------------------------------


@pytest.fixture
def e(db: Session) -> dict:
    """Un autobús en cada centro y un usuario de taller (el plan se crea en cada test con la API)."""
    empresa = crear_empresa(db)
    norte, sur = crear_centro(db, empresa, "Norte"), crear_centro(db, empresa, "Sur")
    autobus = crear_tipo(db, empresa, "Autobús")
    bus_norte = nuevo_vehiculo(empresa, norte, autobus, matricula="1111AAA", km_actuales=100_000)
    bus_sur = nuevo_vehiculo(empresa, sur, autobus, matricula="2222BBB", km_actuales=100_000)
    db.add_all([bus_norte, bus_sur])
    db.flush()
    taller = cabeceras(crear_usuario(db, empresa, "taller@example.com", RolUsuario.TALLER))
    return {"db": db, "empresa": empresa, "norte": norte, "sur": sur, "autobus": autobus,
            "bus_norte": bus_norte, "bus_sur": bus_sur, "taller": taller}


def crear_plan(api: TestClient, e: dict) -> int:
    datos = {"nombre": "Mantenimiento A", "tipo_vehiculo_id": e["autobus"].id, "intervalo_km": 30_000, "intervalo_dias": 365}
    return api.post("/planes", json=datos, headers=e["taller"]).json()["id"]


def realizado(api: TestClient, e: dict, vehiculo: str, plan_id: int, dias_desde: int, km: int) -> None:
    fecha = str(HOY - timedelta(days=dias_desde))
    r = api.post(f"/vehiculos/{e[vehiculo].id}/preventivos/{plan_id}/realizado", json={"fecha": fecha, "km": km}, headers=e["taller"])
    assert r.status_code == 200, r.text


def test_lo_que_esta_al_dia_no_aparece(api: TestClient, e: dict) -> None:
    crear_plan(api, e)  # recién creado: todo al día

    assert api.get("/preventivos/prevision", headers=e["taller"]).json() == []


def test_entran_los_vencidos_y_los_que_tocan_en_30_dias_o_2000_km(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus_norte", plan, dias_desde=10, km=71_000)  # faltan 1.000 km -> próximo
    realizado(api, e, "bus_sur", plan, dias_desde=400, km=95_000)  # vencido por fecha

    prevision = api.get("/preventivos/prevision", headers=e["taller"]).json()

    assert [(p["matricula"], p["situacion"]) for p in prevision] == [("2222BBB", "vencido"), ("1111AAA", "proximo")]


def test_filtros_por_centro_y_tipo(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus_norte", plan, dias_desde=400, km=95_000)
    realizado(api, e, "bus_sur", plan, dias_desde=400, km=95_000)

    def matriculas(**filtros: int) -> list[str]:
        return [p["matricula"] for p in api.get("/preventivos/prevision", params=filtros, headers=e["taller"]).json()]

    assert matriculas(centro_id=e["norte"].id) == ["1111AAA"]
    assert matriculas(tipo_id=e["autobus"].id) == ["1111AAA", "2222BBB"]


def test_no_entran_vehiculos_de_baja_ni_planes_de_baja(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus_norte", plan, dias_desde=400, km=95_000)
    realizado(api, e, "bus_sur", plan, dias_desde=400, km=95_000)
    trafico = cabeceras(crear_usuario(e["db"], e["empresa"], "trafico@example.com", RolUsuario.TRAFICO))

    api.delete(f"/vehiculos/{e['bus_norte'].id}", headers=trafico)
    assert [p["matricula"] for p in api.get("/preventivos/prevision", headers=e["taller"]).json()] == ["2222BBB"]

    api.delete(f"/planes/{plan}", headers=e["taller"])
    assert api.get("/preventivos/prevision", headers=e["taller"]).json() == []


def test_cada_empresa_ve_solo_su_prevision(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus_norte", plan, dias_desde=400, km=95_000)
    ajena = cabeceras(crear_usuario(e["db"], crear_empresa(e["db"], "Otra"), "x@example.com", RolUsuario.TALLER))

    assert api.get("/preventivos/prevision", headers=ajena).json() == []


def test_cualquier_rol_consulta_la_prevision(api: TestClient, e: dict) -> None:
    conductor = cabeceras(crear_usuario(e["db"], e["empresa"], "c@example.com", RolUsuario.CONDUCTOR))

    assert api.get("/preventivos/prevision", headers=conductor).status_code == 200
    assert api.get("/preventivos/prevision").status_code == 401


# --- Alertas del panel -------------------------------------------------------


def test_los_preventivos_aparecen_en_las_alertas_del_panel(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus_sur", plan, dias_desde=400, km=95_000)

    alertas = api.get("/panel", headers=e["taller"]).json()["alertas"]

    assert alertas == [
        {
            "tipo": "preventivo",
            "semaforo": "rojo",
            "vehiculo_id": e["bus_sur"].id,
            "matricula": "2222BBB",
            "mensaje": "Mantenimiento A: Vencido por fecha (hace 35 días)",
            "fecha": str(HOY - timedelta(days=35)),
            "dias_restantes": -35,
        }
    ]


def test_un_preventivo_vencido_no_impide_salir(api: TestClient, e: dict) -> None:
    """La spec solo hace "no apto" por documentación o estado; un preventivo vencido solo avisa."""
    plan = crear_plan(api, e)
    realizado(api, e, "bus_sur", plan, dias_desde=400, km=95_000)

    fila = next(v for v in api.get("/panel", headers=e["taller"]).json()["vehiculos"] if v["matricula"] == "2222BBB")

    assert fila["apto"] is True
