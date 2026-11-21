"""Tests de planes de mantenimiento preventivo por la API (MAN-01).

Criterio: "Un plan 'cada 30.000 km o 12 meses' genera un aviso cuando se cumple la
primera de las dos condiciones". La regla se prueba a fondo en test_reglas_preventivo.py;
aquí, que la API la aplica a los vehículos de verdad.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import RolUsuario
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, nuevo_vehiculo

HOY = date.today()


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    """Empresa con 2 autobuses (100.000 y 50.000 km), 1 camión y un usuario de cada rol."""
    empresa = crear_empresa(db)
    centro = crear_centro(db, empresa)
    autobus, camion = crear_tipo(db, empresa, "Autobús"), crear_tipo(db, empresa, "Camión")
    bus1 = nuevo_vehiculo(empresa, centro, autobus, matricula="1111AAA", km_actuales=100_000)
    bus2 = nuevo_vehiculo(empresa, centro, autobus, matricula="2222BBB", km_actuales=50_000)
    camion1 = nuevo_vehiculo(empresa, centro, camion, matricula="3333CCC", km_actuales=200_000)
    db.add_all([bus1, bus2, camion1])
    db.flush()
    usuarios = {rol: cabeceras(crear_usuario(db, empresa, f"{rol}@example.com", rol)) for rol in RolUsuario}
    return {"db": db, "empresa": empresa, "centro": centro, "autobus": autobus, "camion": camion,
            "bus1": bus1, "bus2": bus2, "camion1": camion1, **usuarios}


PLAN_A = {"nombre": "Mantenimiento A", "intervalo_km": 30_000, "intervalo_dias": 365,
          "tareas": ["Cambio de aceite", "Filtro de aceite", "Filtro de aire"]}


def crear_plan(api: TestClient, e: dict, **cambios: Any) -> dict:
    datos = {**PLAN_A, "tipo_vehiculo_id": e["autobus"].id, **cambios}
    r = api.post("/planes", json=datos, headers=e[RolUsuario.TALLER])
    assert r.status_code == 201, r.text
    return r.json()


def preventivos(api: TestClient, e: dict, vehiculo: str) -> list[dict]:
    return api.get(f"/vehiculos/{e[vehiculo].id}/preventivos", headers=e[RolUsuario.CONDUCTOR]).json()


def realizado(api: TestClient, e: dict, vehiculo: str, plan_id: int, **datos: Any) -> Any:
    return api.post(f"/vehiculos/{e[vehiculo].id}/preventivos/{plan_id}/realizado", json=datos, headers=e[RolUsuario.TALLER])


# --- Crear planes ------------------------------------------------------------


def test_crear_un_plan_con_sus_tareas(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    assert plan["tareas"] == PLAN_A["tareas"]
    assert (plan["intervalo_km"], plan["intervalo_dias"]) == (30_000, 365)
    assert api.get("/planes", headers=e[RolUsuario.CONDUCTOR]).json() == [plan]


def test_los_vehiculos_del_tipo_empiezan_a_contar_desde_hoy(api: TestClient, e: dict) -> None:
    """Sin historial, se cuenta desde hoy y sus km actuales; los de otro tipo no reciben el plan."""
    plan = crear_plan(api, e)

    (p,) = preventivos(api, e, "bus1")
    assert (p["plan_id"], p["ultima_fecha"], p["ultimos_km"]) == (plan["id"], str(HOY), 100_000)
    assert (p["proxima_fecha"], p["proximos_km"]) == (str(HOY + timedelta(days=365)), 130_000)
    assert p["situacion"] == "al_dia"
    assert preventivos(api, e, "bus2")[0]["proximos_km"] == 80_000
    assert preventivos(api, e, "camion1") == []


# --- MAN-01: "lo que llegue antes", de punta a punta -------------------------


def test_vencido_por_km_aunque_no_haya_pasado_el_tiempo(api: TestClient, e: dict) -> None:
    """Caso 1 del criterio: hace 100 días, pero ya ha recorrido 31.000 km."""
    plan = crear_plan(api, e)

    (p,) = realizado(api, e, "bus1", plan["id"], fecha=str(HOY - timedelta(days=100)), km=69_000).json()

    assert p["situacion"] == "vencido"
    assert (p["vencido_por_km"], p["vencido_por_fecha"]) == (True, False)
    assert p["motivo"] == "Vencido por km (se pasó en 1.000 km)"


def test_vencido_por_tiempo_aunque_no_se_hayan_hecho_los_km(api: TestClient, e: dict) -> None:
    """Caso 2 del criterio: solo 1.000 km, pero hace más de 12 meses."""
    plan = crear_plan(api, e)

    (p,) = realizado(api, e, "bus1", plan["id"], fecha=str(HOY - timedelta(days=370)), km=99_000).json()

    assert p["situacion"] == "vencido"
    assert (p["vencido_por_fecha"], p["vencido_por_km"]) == (True, False)
    assert p["motivo"] == "Vencido por fecha (hace 5 días)"


def test_registrar_la_realizacion_de_hoy_lo_deja_al_dia(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)
    realizado(api, e, "bus1", plan["id"], fecha=str(HOY - timedelta(days=400)), km=60_000)

    (p,) = realizado(api, e, "bus1", plan["id"]).json()  # sin datos: hoy y km actuales

    assert (p["ultima_fecha"], p["ultimos_km"], p["situacion"]) == (str(HOY), 100_000, "al_dia")


def test_los_vencidos_salen_primero(api: TestClient, e: dict) -> None:
    crear_plan(api, e, nombre="Revisión anual", intervalo_km=None, intervalo_dias=365, tareas=[])
    frenos = crear_plan(api, e, nombre="Frenos", intervalo_km=60_000, intervalo_dias=None, tareas=[])
    realizado(api, e, "bus1", frenos["id"], km=30_000)

    assert [p["plan_nombre"] for p in preventivos(api, e, "bus1")] == ["Frenos", "Revisión anual"]


# --- Validaciones de la realización ------------------------------------------


def test_realizacion_con_fecha_futura_o_km_imposibles(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    assert realizado(api, e, "bus1", plan["id"], fecha=str(HOY + timedelta(days=1))).status_code == 422
    assert realizado(api, e, "bus1", plan["id"], km=100_001).status_code == 422
    assert realizado(api, e, "bus1", plan["id"], km=-1).status_code == 422


def test_un_plan_de_otro_tipo_no_se_aplica(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    assert realizado(api, e, "camion1", plan["id"]).status_code == 404


# --- Validaciones de los planes ----------------------------------------------


@pytest.mark.parametrize(
    "datos_invalidos",
    [
        {"intervalo_km": None, "intervalo_dias": None},  # ningún intervalo
        {"intervalo_km": 0},
        {"intervalo_dias": -5},
        {"nombre": "  "},
        {"tareas": ["x" * 201]},
    ],
)
def test_planes_invalidos_responden_422(api: TestClient, e: dict, datos_invalidos: dict) -> None:
    datos = {**PLAN_A, "tipo_vehiculo_id": e["autobus"].id, **datos_invalidos}

    assert api.post("/planes", json=datos, headers=e[RolUsuario.TALLER]).status_code == 422


def test_nombre_repetido_en_el_mismo_tipo_responde_409(api: TestClient, e: dict) -> None:
    crear_plan(api, e)

    repetido = api.post("/planes", json={**PLAN_A, "tipo_vehiculo_id": e["autobus"].id}, headers=e[RolUsuario.TALLER])
    otro_tipo = api.post("/planes", json={**PLAN_A, "tipo_vehiculo_id": e["camion"].id}, headers=e[RolUsuario.TALLER])

    assert repetido.status_code == 409
    assert otro_tipo.status_code == 201  # el mismo nombre en otro tipo sí vale
    # Filtrar por tipo de vehículo:
    de_camion = api.get("/planes", params={"tipo_vehiculo_id": e["camion"].id}, headers=e[RolUsuario.TALLER]).json()
    assert [p["tipo_vehiculo_id"] for p in de_camion] == [e["camion"].id]


def test_un_tipo_de_otra_empresa_responde_422(api: TestClient, e: dict) -> None:
    ajeno = crear_tipo(e["db"], crear_empresa(e["db"], "Otra"), "Autobús ajeno")

    r = api.post("/planes", json={**PLAN_A, "tipo_vehiculo_id": ajeno.id}, headers=e[RolUsuario.TALLER])

    assert r.status_code == 422


# --- Editar y dar de baja ----------------------------------------------------


def test_cambiar_el_intervalo_recalcula_los_proximos(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    r = api.patch(f"/planes/{plan['id']}", json={"intervalo_km": 20_000}, headers=e[RolUsuario.TALLER])

    assert r.status_code == 200
    assert preventivos(api, e, "bus1")[0]["proximos_km"] == 120_000
    assert preventivos(api, e, "bus2")[0]["proximos_km"] == 70_000


def test_se_puede_quitar_un_intervalo_pero_no_los_dos(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    solo_km = api.patch(f"/planes/{plan['id']}", json={"intervalo_dias": None}, headers=e[RolUsuario.TALLER])
    ninguno = api.patch(f"/planes/{plan['id']}", json={"intervalo_km": None}, headers=e[RolUsuario.TALLER])

    assert solo_km.status_code == 200
    assert preventivos(api, e, "bus1")[0]["proxima_fecha"] is None
    assert ninguno.status_code == 422


def test_editar_tareas_y_nombre(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    r = api.patch(f"/planes/{plan['id']}", json={"nombre": "Plan A", "tareas": ["Solo aceite"]}, headers=e[RolUsuario.TALLER])
    nulo = api.patch(f"/planes/{plan['id']}", json={"tareas": None}, headers=e[RolUsuario.TALLER])

    assert (r.json()["nombre"], r.json()["tareas"]) == ("Plan A", ["Solo aceite"])
    assert nulo.status_code == 422


def test_un_plan_dado_de_baja_deja_de_aplicarse(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    assert api.delete(f"/planes/{plan['id']}", headers=e[RolUsuario.TALLER]).status_code == 204
    assert preventivos(api, e, "bus1") == []
    assert api.get("/planes", headers=e[RolUsuario.TALLER]).json() == []
    assert api.delete(f"/planes/{plan['id']}", headers=e[RolUsuario.TALLER]).status_code == 404
    assert api.patch(f"/planes/{plan['id']}", json={"nombre": "X"}, headers=e[RolUsuario.TALLER]).status_code == 404


# --- Vehículos nuevos o que cambian de tipo ----------------------------------


def test_un_vehiculo_nuevo_recibe_los_planes_de_su_tipo(api: TestClient, e: dict) -> None:
    crear_plan(api, e)
    datos = {"matricula": "4444DDD", "centro_id": e["centro"].id, "tipo_id": e["autobus"].id, "marca": "M",
             "modelo": "X", "anio": 2022, "combustible": "diesel", "km_actuales": 12_000}

    nuevo = api.post("/vehiculos", json=datos, headers=e[RolUsuario.TRAFICO]).json()

    (p,) = api.get(f"/vehiculos/{nuevo['id']}/preventivos", headers=e[RolUsuario.TALLER]).json()
    assert (p["ultimos_km"], p["proximos_km"]) == (12_000, 42_000)


def test_al_cambiar_de_tipo_cambian_sus_planes(api: TestClient, e: dict) -> None:
    crear_plan(api, e)  # para autobuses
    crear_plan(api, e, nombre="Plan camión", tipo_vehiculo_id=e["camion"].id)

    api.patch(f"/vehiculos/{e['bus1'].id}", json={"tipo_id": e["camion"].id}, headers=e[RolUsuario.TRAFICO])

    assert [p["plan_nombre"] for p in preventivos(api, e, "bus1")] == ["Plan camión"]


# --- Permisos y aislamiento --------------------------------------------------


@pytest.mark.parametrize(("rol", "codigo"), [(RolUsuario.ADMIN, 201), (RolUsuario.TALLER, 201), (RolUsuario.TRAFICO, 403), (RolUsuario.CONDUCTOR, 403)])
def test_quien_puede_crear_planes(api: TestClient, e: dict, rol: RolUsuario, codigo: int) -> None:
    """Spec: el jefe de taller gestiona los planes de mantenimiento (y el gerente)."""
    r = api.post("/planes", json={**PLAN_A, "tipo_vehiculo_id": e["autobus"].id}, headers=e[rol])

    assert r.status_code == codigo


def test_el_conductor_consulta_pero_no_registra_realizaciones(api: TestClient, e: dict) -> None:
    plan = crear_plan(api, e)

    r = api.post(f"/vehiculos/{e['bus1'].id}/preventivos/{plan['id']}/realizado", json={}, headers=e[RolUsuario.CONDUCTOR])

    assert r.status_code == 403
    assert len(preventivos(api, e, "bus1")) == 1


def test_cada_empresa_ve_solo_sus_planes(api: TestClient, e: dict) -> None:
    otra = crear_empresa(e["db"], "Otra")
    ajena = cabeceras(crear_usuario(e["db"], otra, "ajena@example.com", RolUsuario.TALLER))
    plan = crear_plan(api, e)

    assert api.get("/planes", headers=ajena).json() == []
    assert api.get(f"/planes/{plan['id']}", headers=ajena).status_code == 404
    assert api.patch(f"/planes/{plan['id']}", json={"nombre": "X"}, headers=ajena).status_code == 404
    assert api.get(f"/vehiculos/{e['bus1'].id}/preventivos", headers=ajena).status_code == 404
