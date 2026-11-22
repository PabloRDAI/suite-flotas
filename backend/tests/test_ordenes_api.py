"""Tests de órdenes de trabajo por la API (MAN-04, MAN-05, MAN-06 y FLO-03).

- MAN-04: "Al crear una OT desde una avería, la avería queda enlazada y pasa a 'en reparación'."
- MAN-05: "Al cerrar se exigen los km y la fecha; si era preventiva, el plan recalcula la
  siguiente fecha y los siguientes km."
- MAN-06: "El total de la OT es la suma de sus líneas."
- FLO-03: "Con una OT abierta que inmoviliza, 'en taller'; al cerrarla, vuelve a 'operativo'."
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LecturaKm, OrdenTrabajo, Puesto, RolUsuario
from tests.fabricas import (
    cabeceras,
    crear_centro,
    crear_empresa,
    crear_persona,
    crear_tipo,
    crear_usuario,
    crear_vehiculo,
    nuevo_vehiculo,
)

HOY = date.today()


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    """Autobús con 100.000 km (lectura de hace 30 días) y un usuario de cada rol (el plan, con crear_plan)."""
    empresa = crear_empresa(db)
    centro, autobus = crear_centro(db, empresa), crear_tipo(db, empresa, "Autobús")
    vehiculo = nuevo_vehiculo(empresa, centro, autobus, matricula="1111AAA", km_actuales=100_000)
    db.add(vehiculo)
    db.flush()
    db.add(LecturaKm(empresa_id=empresa.id, vehiculo_id=vehiculo.id, fecha=HOY - timedelta(days=30), km=100_000))
    db.flush()
    usuarios = {rol: cabeceras(crear_usuario(db, empresa, f"{rol}@example.com", rol)) for rol in RolUsuario}
    return {"db": db, "empresa": empresa, "centro": centro, "autobus": autobus, "vehiculo": vehiculo, **usuarios}


def taller(e: dict) -> dict[str, str]:
    return e[RolUsuario.TALLER]


def crear_plan(api: TestClient, e: dict) -> int:
    datos = {"nombre": "Mantenimiento A", "tipo_vehiculo_id": e["autobus"].id, "intervalo_km": 30_000,
             "intervalo_dias": 365, "tareas": ["Aceite", "Filtros"]}
    return api.post("/planes", json=datos, headers=taller(e)).json()["id"]


def comunicar_averia(api: TestClient, e: dict, gravedad: str = "inmoviliza") -> dict:
    datos = {"vehiculo_id": str(e["vehiculo"].id), "descripcion": "No arranca", "gravedad": gravedad}
    return api.post("/averias", data=datos, headers=e[RolUsuario.CONDUCTOR]).json()


def crear_ot(api: TestClient, e: dict, **datos: Any) -> Any:
    return api.post("/ordenes-trabajo", json=datos, headers=taller(e))


def ot_manual(api: TestClient, e: dict, inmoviliza: bool = True) -> dict:
    r = crear_ot(api, e, vehiculo_id=e["vehiculo"].id, tipo="correctiva", descripcion="Revisar ruido", inmoviliza=inmoviliza)
    assert r.status_code == 201, r.text
    return r.json()


def accion(api: TestClient, e: dict, ot: dict, nombre: str, **datos: Any) -> Any:
    return api.post(f"/ordenes-trabajo/{ot['id']}/{nombre}", json=datos, headers=taller(e))


def cerrar(api: TestClient, e: dict, ot: dict, km: int = 100_500, **datos: Any) -> Any:
    accion(api, e, ot, "iniciar")
    return accion(api, e, ot, "cerrar", km=km, **datos)


def estado_vehiculo(api: TestClient, e: dict) -> str:
    return api.get(f"/vehiculos/{e['vehiculo'].id}", headers=taller(e)).json()["estado"]


# --- MAN-04: crear desde una avería ------------------------------------------


def test_desde_una_averia_queda_enlazada_y_en_reparacion(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-04."""
    averia = comunicar_averia(api, e, "inmoviliza")
    assert averia["estado_vehiculo"] == "inmovilizado"

    r = crear_ot(api, e, averia_id=averia["id"])

    assert r.status_code == 201
    ot = r.json()
    assert (ot["averia_id"], ot["tipo"], ot["origen"], ot["estado"]) == (averia["id"], "correctiva", "averia", "abierta")
    assert ot["inmoviliza"] is True  # hereda que inmoviliza
    assert ot["descripcion"] == "No arranca"  # y la descripción de la avería
    assert api.get(f"/averias/{averia['id']}", headers=taller(e)).json()["estado"] == "en_reparacion"
    assert ot["estado_vehiculo"] == "en_taller"  # de "inmovilizado" pasa a "en taller"


def test_una_averia_que_inmoviliza_no_admite_una_ot_que_no_inmovilice(api: TestClient, e: dict) -> None:
    """Si no, el vehículo pasaría a "operativo" con la avería sin reparar."""
    averia = comunicar_averia(api, e, "inmoviliza")

    assert crear_ot(api, e, averia_id=averia["id"], inmoviliza=False).status_code == 422


def test_una_averia_leve_genera_una_ot_que_no_inmoviliza(api: TestClient, e: dict) -> None:
    ot = crear_ot(api, e, averia_id=comunicar_averia(api, e, "leve")["id"]).json()

    assert ot["inmoviliza"] is False
    assert ot["estado_vehiculo"] == "operativo"


def test_una_averia_solo_tiene_una_ot_abierta(api: TestClient, e: dict) -> None:
    averia = comunicar_averia(api, e)
    crear_ot(api, e, averia_id=averia["id"])

    assert crear_ot(api, e, averia_id=averia["id"]).status_code == 409


# --- MAN-04: desde un plan y a mano ------------------------------------------


def test_desde_un_plan_es_preventiva_con_sus_tareas(api: TestClient, e: dict) -> None:
    plan_id = crear_plan(api, e)

    ot = crear_ot(api, e, vehiculo_id=e["vehiculo"].id, plan_id=plan_id).json()

    assert (ot["tipo"], ot["origen"], ot["plan_id"], ot["plan_nombre"]) == ("preventiva", "plan", plan_id, "Mantenimiento A")
    assert ot["descripcion"] == "Mantenimiento A: Aceite; Filtros"
    assert ot["inmoviliza"] is True


def test_un_plan_de_otro_tipo_no_vale(api: TestClient, e: dict) -> None:
    plan_id = crear_plan(api, e)
    camion = crear_vehiculo(e["db"], e["empresa"], "2222BBB")  # de otro tipo

    assert crear_ot(api, e, vehiculo_id=camion.id, plan_id=plan_id).status_code == 422


@pytest.mark.parametrize(
    "datos",
    [
        {"tipo": "correctiva"},  # manual sin descripción ni vehículo
        {"vehiculo_id": 1, "descripcion": "x"},  # manual sin tipo
        {"averia_id": 1, "plan_id": 1},  # de las dos formas a la vez
        {"vehiculo_id": 1, "tipo": "urgente", "descripcion": "x"},  # tipo que no existe
    ],
)
def test_datos_de_creacion_invalidos(api: TestClient, e: dict, datos: dict) -> None:
    assert crear_ot(api, e, **datos).status_code == 422


# --- FLO-03: el estado del vehículo, de punta a punta ------------------------


def test_flo_03_en_taller_mientras_esta_abierta_y_operativo_al_cerrarla(api: TestClient, e: dict) -> None:
    """Criterio literal de FLO-03 con datos reales."""
    ot = ot_manual(api, e, inmoviliza=True)
    assert estado_vehiculo(api, e) == "en_taller"

    accion(api, e, ot, "iniciar")
    assert estado_vehiculo(api, e) == "en_taller"

    cerrar_r = accion(api, e, ot, "cerrar", km=100_200)
    assert cerrar_r.json()["estado_vehiculo"] == "operativo"
    assert estado_vehiculo(api, e) == "operativo"


def test_una_ot_que_no_inmoviliza_no_cambia_el_estado(api: TestClient, e: dict) -> None:
    ot_manual(api, e, inmoviliza=False)

    assert estado_vehiculo(api, e) == "operativo"


def test_cambiar_inmoviliza_recalcula_el_estado(api: TestClient, e: dict) -> None:
    ot = ot_manual(api, e, inmoviliza=False)

    r = api.patch(f"/ordenes-trabajo/{ot['id']}", json={"inmoviliza": True}, headers=taller(e))

    assert r.json()["estado_vehiculo"] == "en_taller"


# --- MAN-05: flujo y cierre --------------------------------------------------


def test_no_se_cierra_sin_pasar_por_en_curso(api: TestClient, e: dict) -> None:
    ot = ot_manual(api, e)

    r = accion(api, e, ot, "cerrar", km=100_500)

    assert r.status_code == 409
    assert "Siguiente estado posible" in r.json()["detail"]


def test_al_cerrar_se_exigen_los_km(api: TestClient, e: dict) -> None:
    """Criterio de MAN-05: sin km no se cierra (y la BD lo impide también, ver el último test)."""
    ot = ot_manual(api, e)
    accion(api, e, ot, "iniciar")

    assert accion(api, e, ot, "cerrar").status_code == 422


def test_cerrar_registra_los_km_como_lectura(api: TestClient, e: dict) -> None:
    ot = ot_manual(api, e)

    cerrada = cerrar(api, e, ot, km=100_700, trabajo_realizado="Rodamiento sustituido").json()

    assert (cerrada["estado"], cerrada["km_cierre"], cerrada["fecha_cierre"]) == ("cerrada", 100_700, str(HOY))
    assert cerrada["trabajo_realizado"] == "Rodamiento sustituido"
    assert api.get(f"/vehiculos/{e['vehiculo'].id}", headers=taller(e)).json()["km_actuales"] == 100_700
    lecturas = api.get(f"/vehiculos/{e['vehiculo'].id}/km", headers=taller(e)).json()
    assert (lecturas[0]["fecha"], lecturas[0]["km"]) == (str(HOY), 100_700)


@pytest.mark.parametrize(
    ("datos", "texto"),
    [
        ({"km": 99_000}, "menores que los de la lectura anterior"),  # los km no retroceden (FLO-05)
        ({"km": 100_500, "fecha": str(HOY + timedelta(days=1))}, "futura"),
        ({"km": 100_500, "fecha": str(HOY - timedelta(days=5))}, "anterior a la apertura"),
    ],
)
def test_cierres_no_validos(api: TestClient, e: dict, datos: dict, texto: str) -> None:
    ot = ot_manual(api, e)
    accion(api, e, ot, "iniciar")

    r = accion(api, e, ot, "cerrar", **datos)

    assert r.status_code == 422
    assert texto in r.json()["detail"]
    assert api.get(f"/ordenes-trabajo/{ot['id']}", headers=taller(e)).json()["estado"] == "en_curso"  # no cambia nada


def test_al_cerrar_una_preventiva_el_plan_recalcula_el_proximo(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-05."""
    plan_id = crear_plan(api, e)
    ot = crear_ot(api, e, vehiculo_id=e["vehiculo"].id, plan_id=plan_id).json()

    cerrar(api, e, ot, km=100_900)

    (p,) = api.get(f"/vehiculos/{e['vehiculo'].id}/preventivos", headers=taller(e)).json()
    assert (p["ultima_fecha"], p["ultimos_km"]) == (str(HOY), 100_900)
    assert (p["proxima_fecha"], p["proximos_km"]) == (str(HOY + timedelta(days=365)), 130_900)


def test_al_cerrar_la_ot_de_una_averia_esta_queda_resuelta(api: TestClient, e: dict) -> None:
    averia = comunicar_averia(api, e, "inmoviliza")
    ot = crear_ot(api, e, averia_id=averia["id"]).json()

    cerrada = cerrar(api, e, ot, trabajo_realizado="Alternador nuevo").json()

    a = api.get(f"/averias/{averia['id']}", headers=taller(e)).json()
    assert (a["estado"], a["nota_resolucion"]) == ("resuelta", "Alternador nuevo")
    assert cerrada["estado_vehiculo"] == "operativo"


def test_cancelar_devuelve_la_averia_a_comunicada_y_el_vehiculo_a_inmovilizado(api: TestClient, e: dict) -> None:
    averia = comunicar_averia(api, e, "inmoviliza")
    ot = crear_ot(api, e, averia_id=averia["id"]).json()

    r = accion(api, e, ot, "cancelar", motivo="Se repara en otro taller")

    assert (r.json()["estado"], r.json()["motivo_cancelacion"]) == ("cancelada", "Se repara en otro taller")
    assert api.get(f"/averias/{averia['id']}", headers=taller(e)).json()["estado"] == "comunicada"
    assert r.json()["estado_vehiculo"] == "inmovilizado"  # la avería sigue sin reparar
    assert crear_ot(api, e, averia_id=averia["id"]).status_code == 201  # se puede abrir otra


def test_una_ot_cerrada_o_cancelada_es_definitiva(api: TestClient, e: dict) -> None:
    cerrada = ot_manual(api, e)
    cerrar(api, e, cerrada)
    cancelada = ot_manual(api, e)
    accion(api, e, cancelada, "cancelar")

    for ot in (cerrada, cancelada):
        assert accion(api, e, ot, "iniciar").status_code == 409
        assert accion(api, e, ot, "cancelar").status_code == 409
        linea = {"concepto": "recambio", "descripcion": "x", "cantidad": 1, "precio_unitario": 1}
        assert api.post(f"/ordenes-trabajo/{ot['id']}/lineas", json=linea, headers=taller(e)).status_code == 409
        assert api.patch(f"/ordenes-trabajo/{ot['id']}", json={"descripcion": "x"}, headers=taller(e)).status_code == 409


# --- MAN-06: coste -----------------------------------------------------------


def anadir(api: TestClient, e: dict, ot: dict, concepto: str, cantidad: Any, precio: Any, descripcion: str = "x") -> Any:
    linea = {"concepto": concepto, "descripcion": descripcion, "cantidad": cantidad, "precio_unitario": precio}
    return api.post(f"/ordenes-trabajo/{ot['id']}/lineas", json=linea, headers=taller(e))


def test_el_total_es_la_suma_de_las_lineas(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-06, por la API."""
    ot = ot_manual(api, e)
    anadir(api, e, ot, "mano_obra", "2.5", "45.00", "Diagnóstico y reparación")
    anadir(api, e, ot, "recambio", 3, "14.95", "Filtro")
    r = anadir(api, e, ot, "externo", 1, 180, "Rectificado de discos")

    assert r.status_code == 201
    c = r.json()["coste"]
    assert (c["mano_obra"], c["recambios"], c["externos"], c["total"]) == (112.5, 44.85, 180.0, 337.35)
    assert c["total"] == pytest.approx(sum(l["importe"] for l in r.json()["lineas"]))


def test_quitar_una_linea_actualiza_el_coste(api: TestClient, e: dict) -> None:
    ot = ot_manual(api, e)
    anadir(api, e, ot, "recambio", 1, 100)
    linea = anadir(api, e, ot, "recambio", 1, 50).json()["lineas"][-1]

    assert api.delete(f"/ordenes-trabajo/{ot['id']}/lineas/{linea['id']}", headers=taller(e)).status_code == 204
    assert api.get(f"/ordenes-trabajo/{ot['id']}", headers=taller(e)).json()["coste"]["total"] == 100.0


@pytest.mark.parametrize(
    ("cantidad", "precio"), [(0, 10), (-1, 10), (1, -5), ("1.234", 10), (1, "abc")]
)
def test_lineas_invalidas(api: TestClient, e: dict, cantidad: Any, precio: Any) -> None:
    """Cantidad positiva, precio no negativo y como mucho 2 decimales."""
    assert anadir(api, e, ot_manual(api, e), "recambio", cantidad, precio).status_code == 422


# --- Responsable, listado, permisos y aislamiento ----------------------------


def test_responsable_de_la_ot(api: TestClient, e: dict) -> None:
    mecanico = crear_persona(e["db"], e["empresa"], "Mario", Puesto.MECANICO, e["centro"])
    ajeno = crear_persona(e["db"], crear_empresa(e["db"], "Otra"), "Ajeno")
    base = {"vehiculo_id": e["vehiculo"].id, "tipo": "correctiva", "descripcion": "x"}

    assert crear_ot(api, e, **base, responsable_id=mecanico.id).json()["responsable_nombre"] == "Mario"
    assert crear_ot(api, e, **base, responsable_id=ajeno.id).status_code == 422


def test_listado_con_filtros(api: TestClient, e: dict) -> None:
    abierta = ot_manual(api, e, inmoviliza=False)
    cerrada = ot_manual(api, e, inmoviliza=False)
    cerrar(api, e, cerrada)
    plan_id = crear_plan(api, e)
    preventiva = crear_ot(api, e, vehiculo_id=e["vehiculo"].id, plan_id=plan_id).json()

    def ids(**filtros: Any) -> list[int]:
        return [o["id"] for o in api.get("/ordenes-trabajo", params=filtros, headers=e[RolUsuario.CONDUCTOR]).json()]

    assert ids() == [preventiva["id"], cerrada["id"], abierta["id"]]  # más reciente primero
    assert ids(abiertas=True) == [preventiva["id"], abierta["id"]]
    assert ids(estado="cerrada") == [cerrada["id"]]
    assert ids(tipo="preventiva") == [preventiva["id"]]


@pytest.mark.parametrize("rol", [RolUsuario.TRAFICO, RolUsuario.CONDUCTOR])
def test_trafico_y_conductor_consultan_pero_no_gestionan(api: TestClient, e: dict, rol: RolUsuario) -> None:
    ot = ot_manual(api, e)
    datos = {"vehiculo_id": e["vehiculo"].id, "tipo": "correctiva", "descripcion": "x"}

    assert api.post("/ordenes-trabajo", json=datos, headers=e[rol]).status_code == 403
    assert api.post(f"/ordenes-trabajo/{ot['id']}/iniciar", json={}, headers=e[rol]).status_code == 403
    assert api.get(f"/ordenes-trabajo/{ot['id']}", headers=e[rol]).status_code == 200


def test_cada_empresa_solo_ve_sus_ordenes(api: TestClient, e: dict) -> None:
    ot = ot_manual(api, e)
    averia = comunicar_averia(api, e)
    otra = crear_empresa(e["db"], "Otra")
    ajena = cabeceras(crear_usuario(e["db"], otra, "x@example.com", RolUsuario.TALLER))

    assert api.get("/ordenes-trabajo", headers=ajena).json() == []
    assert api.get(f"/ordenes-trabajo/{ot['id']}", headers=ajena).status_code == 404
    assert api.post(f"/ordenes-trabajo/{ot['id']}/iniciar", json={}, headers=ajena).status_code == 404
    assert api.post("/ordenes-trabajo", json={"averia_id": averia["id"]}, headers=ajena).status_code == 422


def test_la_bd_no_admite_una_ot_cerrada_sin_km(db: Session, e: dict) -> None:
    """MAN-05 también como restricción de la base de datos (última barrera)."""
    db.add(OrdenTrabajo(empresa_id=e["empresa"].id, vehiculo_id=e["vehiculo"].id, tipo="correctiva",
                        origen="manual", estado="cerrada", inmoviliza=False, descripcion="x", fecha_cierre=HOY))

    with pytest.raises(IntegrityError, match="ck_orden_trabajo_cerrada_con_fecha_y_km"):
        db.flush()
