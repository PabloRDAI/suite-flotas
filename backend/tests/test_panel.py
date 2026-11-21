"""Tests del panel de flota (FLO-04).

Criterio de aceptación: "El panel muestra totales por estado que coinciden con
el listado filtrado; carga en menos de 1 s con 150 vehículos."
"""

import time
from collections import Counter
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EstadoVehiculo, RolUsuario, Vehiculo, Vencimiento
from app.servicios.demo import PASSWORD_DEMO, crear_empresa_demo, email_demo
from app.servicios.panel import _mensaje_vencimiento
from tests.fabricas import (
    cabeceras,
    crear_centro,
    crear_empresa,
    crear_tipo,
    crear_tipo_vencimiento,
    crear_usuario,
    crear_vehiculo,
    nuevo_vehiculo,
)

HOY = date.today()


def en(dias: int) -> date:
    return HOY + timedelta(days=dias)


def venc(vehiculo: Vehiculo, tipo_id: int, dias: int) -> Vencimiento:
    return Vencimiento(empresa_id=vehiculo.empresa_id, vehiculo_id=vehiculo.id, tipo_id=tipo_id, fecha_caducidad=en(dias))


@pytest.fixture
def flota(db: Session) -> dict:
    """3 vehículos: uno en regla, uno con la ITV caducada y uno con el seguro en ámbar."""
    empresa = crear_empresa(db)
    itv = crear_tipo_vencimiento(db, empresa, "ITV", dias_aviso=30)
    seguro = crear_tipo_vencimiento(db, empresa, "Seguro", dias_aviso=30)
    en_regla = crear_vehiculo(db, empresa, "1111AAA")
    sin_itv = crear_vehiculo(db, empresa, "2222BBB")
    ambar = crear_vehiculo(db, empresa, "3333CCC")
    db.add_all(
        [
            venc(en_regla, itv.id, 200),
            venc(en_regla, seguro.id, 200),
            venc(sin_itv, itv.id, -400),  # ITV antigua: historial, no debe generar alerta
            venc(sin_itv, itv.id, -5),  # ITV vigente: caducada hace 5 días -> no apto
            venc(ambar, seguro.id, 10),
        ]
    )
    db.flush()
    auth = cabeceras(crear_usuario(db, empresa, "trafico@example.com", RolUsuario.TRAFICO))
    return {"db": db, "empresa": empresa, "auth": auth, "en_regla": en_regla, "sin_itv": sin_itv, "ambar": ambar}


def panel(api: TestClient, auth: dict, **filtros: int) -> dict:
    respuesta = api.get("/panel", params=filtros, headers=auth)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


# --- Contadores coherentes con la tabla --------------------------------------


def test_los_totales_coinciden_con_el_listado(api: TestClient, flota: dict) -> None:
    """Criterio literal de FLO-04 (sin filtro)."""
    datos = panel(api, flota["auth"])
    c = datos["contadores"]
    por_estado = Counter(v["estado"] for v in datos["vehiculos"])

    assert c["total"] == len(datos["vehiculos"]) == 3
    assert c["operativo"] == por_estado["operativo"]
    assert c["en_taller"] == por_estado["en_taller"]
    assert c["inmovilizado"] == por_estado["inmovilizado"]
    assert c["aptos"] + c["no_aptos"] == c["total"]
    assert c["no_aptos"] == sum(1 for v in datos["vehiculos"] if not v["apto"])


def test_los_totales_coinciden_con_el_listado_filtrado(api: TestClient, flota: dict) -> None:
    """Criterio literal de FLO-04 (con filtro por centro)."""
    centro = flota["sin_itv"].centro_id

    datos = panel(api, flota["auth"], centro_id=centro)

    assert [v["matricula"] for v in datos["vehiculos"]] == ["2222BBB"]
    assert datos["contadores"]["total"] == 1
    assert datos["contadores"]["no_aptos"] == 1
    assert {a["matricula"] for a in datos["alertas"]} == {"2222BBB"}  # las alertas también se filtran


def test_filtro_por_tipo(api: TestClient, flota: dict) -> None:
    datos = panel(api, flota["auth"], tipo_id=flota["ambar"].tipo_id)

    assert [v["matricula"] for v in datos["vehiculos"]] == ["3333CCC"]


def test_un_vehiculo_en_taller_se_cuenta_como_tal(api: TestClient, flota: dict) -> None:
    flota["en_regla"].estado = EstadoVehiculo.EN_TALLER
    flota["db"].flush()

    c = panel(api, flota["auth"])["contadores"]

    assert (c["operativo"], c["en_taller"], c["inmovilizado"]) == (2, 1, 0)


def test_los_vehiculos_de_baja_no_aparecen(api: TestClient, flota: dict) -> None:
    api.delete(f"/vehiculos/{flota['en_regla'].id}", headers=flota["auth"])

    datos = panel(api, flota["auth"])

    assert datos["contadores"]["total"] == 2
    assert "1111AAA" not in [v["matricula"] for v in datos["vehiculos"]]


# --- Aptitud y alertas -------------------------------------------------------


def test_con_la_itv_caducada_aparece_como_no_apto_aunque_este_operativo(api: TestClient, flota: dict) -> None:
    """FLO-07 en el panel."""
    fila = next(v for v in panel(api, flota["auth"])["vehiculos"] if v["matricula"] == "2222BBB")

    assert fila["estado"] == "operativo"
    assert fila["apto"] is False
    assert fila["semaforo"] == "rojo"
    assert fila["motivos"][0].startswith("ITV: caducó el")


def test_las_alertas_van_de_lo_mas_urgente_a_lo_menos(api: TestClient, flota: dict) -> None:
    alertas = panel(api, flota["auth"])["alertas"]

    assert [(a["matricula"], a["semaforo"]) for a in alertas] == [("2222BBB", "rojo"), ("3333CCC", "ambar")]
    assert alertas[0]["mensaje"] == "ITV: caducó hace 5 días"
    assert alertas[1]["mensaje"] == "Seguro: caduca en 10 días"
    assert alertas[0]["tipo"] == "vencimiento"


def test_un_documento_renovado_no_genera_alerta(api: TestClient, flota: dict) -> None:
    """La ITV de hace 400 días es historial: solo alerta la vigente (hace 5 días)."""
    alertas = panel(api, flota["auth"])["alertas"]

    assert sum(1 for a in alertas if a["matricula"] == "2222BBB") == 1


def test_cada_empresa_ve_solo_su_panel(api: TestClient, flota: dict) -> None:
    crear_vehiculo(flota["db"], crear_empresa(flota["db"], "Otra empresa"), "9999ZZZ")

    datos = panel(api, flota["auth"])

    assert "9999ZZZ" not in [v["matricula"] for v in datos["vehiculos"]]
    assert datos["contadores"]["total"] == 3


def test_cualquier_rol_puede_ver_el_panel(api: TestClient, flota: dict) -> None:
    conductor = cabeceras(crear_usuario(flota["db"], flota["empresa"], "c@example.com", RolUsuario.CONDUCTOR))

    assert api.get("/panel", headers=conductor).status_code == 200
    assert api.get("/panel").status_code == 401  # pero hace falta sesión


def test_panel_de_una_empresa_sin_vehiculos(api: TestClient, db: Session) -> None:
    auth = cabeceras(crear_usuario(db, crear_empresa(db)))

    datos = panel(api, auth)

    assert datos["contadores"]["total"] == 0
    assert datos["vehiculos"] == datos["alertas"] == []


def test_panel_de_la_empresa_demo(api: TestClient, db: Session) -> None:
    """Con los datos demo: 25 vehículos, 2 no aptos y alertas de documentación y de preventivos."""
    crear_empresa_demo(db, hoy=HOY)
    token = api.post("/auth/login", json={"email": email_demo("trafico"), "password": PASSWORD_DEMO}).json()
    datos = panel(api, {"Authorization": f"Bearer {token['access_token']}"})

    assert datos["contadores"]["total"] == 25
    assert datos["contadores"]["no_aptos"] == 2
    por_tipo = Counter((a["tipo"], a["semaforo"]) for a in datos["alertas"])
    assert por_tipo == {
        ("vencimiento", "rojo"): 3, ("vencimiento", "ambar"): 3,  # documentación (FLO-06)
        ("preventivo", "rojo"): 2, ("preventivo", "ambar"): 2,  # mantenimiento (MAN-02)
    }


@pytest.mark.parametrize(
    ("dias", "mensaje"),
    [
        (-5, "ITV: caducó hace 5 días"),
        (-1, "ITV: caducó hace 1 día"),
        (0, "ITV: caduca hoy"),
        (1, "ITV: caduca en 1 día"),
        (12, "ITV: caduca en 12 días"),
    ],
)
def test_mensajes_de_las_alertas(dias: int, mensaje: str) -> None:
    assert _mensaje_vencimiento("ITV", dias) == mensaje


# --- Rendimiento -------------------------------------------------------------


def test_carga_en_menos_de_un_segundo_con_150_vehiculos(api: TestClient, db: Session) -> None:
    """Criterio literal de FLO-04: 150 vehículos con 5 documentos cada uno."""
    empresa = crear_empresa(db)
    centro, tipo = crear_centro(db, empresa), crear_tipo(db, empresa)
    tipos_venc = [crear_tipo_vencimiento(db, empresa, f"Documento {i}") for i in range(5)]
    vehiculos = [nuevo_vehiculo(empresa, centro, tipo, matricula=f"{i:04d}PRF") for i in range(150)]
    db.add_all(vehiculos)
    db.flush()
    db.add_all(venc(v, t.id, (i * 7) % 400 - 30) for i, v in enumerate(vehiculos) for t in tipos_venc)
    db.flush()
    auth = cabeceras(crear_usuario(db, empresa))

    inicio = time.perf_counter()
    datos = panel(api, auth)
    duracion = time.perf_counter() - inicio

    assert datos["contadores"]["total"] == 150
    assert duracion < 1.0, f"El panel tardó {duracion:.2f} s"
