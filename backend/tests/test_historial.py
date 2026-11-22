"""Tests del historial de mantenimiento por vehículo (MAN-07) y de los apoyos del tablero de taller.

Criterio de MAN-07: "La ficha del vehículo lista todas sus OT con fecha, tipo, km y coste."
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import LecturaKm, RolUsuario
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, crear_vehiculo, nuevo_vehiculo

HOY = date.today()


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    empresa = crear_empresa(db)
    vehiculo = nuevo_vehiculo(empresa, crear_centro(db, empresa), crear_tipo(db, empresa), matricula="1111AAA", km_actuales=50_000)
    db.add(vehiculo)
    db.flush()
    db.add(LecturaKm(empresa_id=empresa.id, vehiculo_id=vehiculo.id, fecha=HOY - timedelta(days=10), km=50_000))
    db.flush()
    taller = cabeceras(crear_usuario(db, empresa, "taller@example.com", RolUsuario.TALLER))
    conductor = cabeceras(crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR))
    return {"db": db, "empresa": empresa, "vehiculo": vehiculo, "taller": taller, "conductor": conductor}


def nueva_ot(api: TestClient, e: dict, tipo: str, descripcion: str, lineas: list[tuple[str, float, float]]) -> dict:
    ot = api.post("/ordenes-trabajo", json={"vehiculo_id": e["vehiculo"].id, "tipo": tipo, "descripcion": descripcion}, headers=e["taller"]).json()
    for concepto, cantidad, precio in lineas:
        api.post(f"/ordenes-trabajo/{ot['id']}/lineas", json={"concepto": concepto, "descripcion": "x", "cantidad": cantidad, "precio_unitario": precio}, headers=e["taller"])
    return ot


def cerrar(api: TestClient, e: dict, ot: dict, km: int) -> None:
    api.post(f"/ordenes-trabajo/{ot['id']}/iniciar", json={}, headers=e["taller"])
    r = api.post(f"/ordenes-trabajo/{ot['id']}/cerrar", json={"km": km}, headers=e["taller"])
    assert r.status_code == 200, r.text


def historial(api: TestClient, e: dict) -> dict:
    return api.get(f"/vehiculos/{e['vehiculo'].id}/historial", headers=e["conductor"]).json()


# --- MAN-07 ------------------------------------------------------------------


def test_lista_todas_sus_ot_con_fecha_tipo_km_y_coste(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-07."""
    preventiva = nueva_ot(api, e, "preventiva", "Cambio de aceite", [("mano_obra", 1.5, 45), ("recambio", 1, 80)])
    cerrar(api, e, preventiva, km=50_200)
    correctiva = nueva_ot(api, e, "correctiva", "Pinchazo", [("recambio", 1, 250)])
    cerrar(api, e, correctiva, km=50_300)
    abierta = nueva_ot(api, e, "correctiva", "Ruido en la suspensión", [("mano_obra", 2, 45)])

    h = historial(api, e)

    assert [(o["ot_id"], o["tipo"], o["estado"], o["km"], o["coste"]) for o in h["ordenes"]] == [
        (abierta["id"], "correctiva", "abierta", None, 90.0),  # la más reciente primero
        (correctiva["id"], "correctiva", "cerrada", 50_300, 250.0),
        (preventiva["id"], "preventiva", "cerrada", 50_200, 147.5),
    ]
    assert all(o["fecha"] == str(HOY) for o in h["ordenes"])


def test_el_resumen_solo_cuenta_lo_cerrado(api: TestClient, e: dict) -> None:
    """Lo gastado = OT cerradas; separado en preventivo y correctivo (base de MAN-08)."""
    cerrar(api, e, nueva_ot(api, e, "preventiva", "Aceite", [("recambio", 1, 100)]), km=50_100)
    cerrar(api, e, nueva_ot(api, e, "correctiva", "Frenos", [("recambio", 1, 300), ("mano_obra", 2, 45)]), km=50_200)
    nueva_ot(api, e, "correctiva", "Abierta: no cuenta", [("recambio", 1, 999)])

    assert historial(api, e)["resumen"] == {
        "ordenes": 3,
        "cerradas": 2,
        "coste_total": 490.0,
        "coste_preventivo": 100.0,
        "coste_correctivo": 390.0,
    }


def test_un_vehiculo_sin_ordenes(api: TestClient, e: dict) -> None:
    h = historial(api, e)

    assert h["ordenes"] == []
    assert h["resumen"]["coste_total"] == 0


def test_historial_de_otra_empresa_404(api: TestClient, e: dict) -> None:
    ajeno = crear_vehiculo(e["db"], crear_empresa(e["db"], "Otra"), "9999ZZZ")

    assert api.get(f"/vehiculos/{ajeno.id}/historial", headers=e["taller"]).status_code == 404


# --- Apoyos del tablero de taller --------------------------------------------


def test_las_averias_indican_su_orden_de_trabajo(api: TestClient, e: dict) -> None:
    averia = api.post(
        "/averias", data={"vehiculo_id": str(e["vehiculo"].id), "descripcion": "No arranca", "gravedad": "grave"}, headers=e["conductor"]
    ).json()
    assert averia["orden_trabajo_id"] is None

    ot = api.post("/ordenes-trabajo", json={"averia_id": averia["id"]}, headers=e["taller"]).json()

    assert api.get(f"/averias/{averia['id']}", headers=e["taller"]).json()["orden_trabajo_id"] == ot["id"]
    assert api.get("/averias", headers=e["taller"]).json()[0]["orden_trabajo_id"] == ot["id"]


def test_filtro_de_cerradas_recientes(api: TestClient, e: dict) -> None:
    ot = nueva_ot(api, e, "correctiva", "x", [])
    cerrar(api, e, ot, km=50_100)
    nueva_ot(api, e, "correctiva", "abierta", [])

    recientes = api.get("/ordenes-trabajo", params={"cerradas_desde": str(HOY - timedelta(days=30))}, headers=e["taller"]).json()
    futuras = api.get("/ordenes-trabajo", params={"cerradas_desde": str(HOY + timedelta(days=1))}, headers=e["taller"]).json()

    assert [o["id"] for o in recientes] == [ot["id"]]  # solo las cerradas, no la abierta
    assert futuras == []


def test_una_averia_con_ot_abierta_no_se_resuelve_directamente(api: TestClient, e: dict) -> None:
    """Se resuelve cerrando su OT; si no, quedaría "resuelta" con la OT todavía en marcha."""
    averia = api.post(
        "/averias", data={"vehiculo_id": str(e["vehiculo"].id), "descripcion": "Fuga", "gravedad": "grave"}, headers=e["conductor"]
    ).json()
    api.post("/ordenes-trabajo", json={"averia_id": averia["id"]}, headers=e["taller"])

    r = api.post(f"/averias/{averia['id']}/resolver", json={}, headers=e["taller"])

    assert r.status_code == 409
    assert "ciérrala" in r.json()["detail"]
