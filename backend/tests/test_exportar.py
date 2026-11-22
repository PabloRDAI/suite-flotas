"""Exportación a Excel de los listados (GEN-06).

Criterio: "Cada listado tiene un botón que descarga un .xlsx con los filtros aplicados."
Cada test descarga el Excel con unos filtros y comprueba que trae exactamente las filas que
devuelve el listado (o la pantalla) con esos mismos filtros.
"""

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import RolUsuario
from app.servicios.demo import PASSWORD_DEMO, crear_empresa_demo, email_demo
from app.servicios.excel import TIPO_XLSX
from tests.fabricas import cabeceras, crear_empresa, crear_usuario

HOY = date.today()


@pytest.fixture
def auth(api: TestClient, db: Session) -> dict[str, str]:
    crear_empresa_demo(db, hoy=HOY)
    r = api.post("/auth/login", json={"email": email_demo("admin"), "password": PASSWORD_DEMO})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def descargar(api: TestClient, auth: dict, ruta: str, **filtros: Any) -> list[list[Any]]:
    """Descarga el Excel y devuelve sus filas (la primera es la cabecera)."""
    r = api.get(ruta, params=filtros, headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == TIPO_XLSX
    hoja = load_workbook(BytesIO(r.content)).active
    return [list(fila) for fila in hoja.iter_rows(values_only=True)]


def listar(api: TestClient, auth: dict, ruta: str, **filtros: Any) -> list[dict]:
    return api.get(ruta, params=filtros, headers=auth).json()


def ids_tipo_y_centro(api: TestClient, auth: dict) -> tuple[int, int]:
    tipo = next(t["id"] for t in listar(api, auth, "/tipos-vehiculo") if t["nombre"] == "Cisterna")
    return tipo, listar(api, auth, "/centros")[0]["id"]


# --- Vehículos ---------------------------------------------------------------


def test_vehiculos_sin_filtros(api: TestClient, auth: dict) -> None:
    filas = descargar(api, auth, "/vehiculos/exportar")

    assert filas[0][:3] == ["Matrícula", "Tipo", "Centro"]
    assert [f[0] for f in filas[1:]] == [v["matricula"] for v in listar(api, auth, "/vehiculos")]


def test_vehiculos_con_los_filtros_de_la_pantalla(api: TestClient, auth: dict) -> None:
    """Centro y tipo (los filtra la API) + estado y búsqueda (los filtra la pantalla)."""
    tipo, _ = ids_tipo_y_centro(api, auth)
    todos = listar(api, auth, "/vehiculos")
    con_taller = next(v for v in todos if v["estado"] == "en_taller")

    # Por tipo: las 3 cisternas.
    assert len(descargar(api, auth, "/vehiculos/exportar", tipo_id=tipo)) == 1 + 3
    # Por estado: el que está en el taller.
    assert [f[0] for f in descargar(api, auth, "/vehiculos/exportar", estado="en_taller")[1:]] == [con_taller["matricula"]]
    # Búsqueda como en la pantalla: sin distinguir mayúsculas, espacios ni guiones en la matrícula.
    m = con_taller["matricula"]
    buscado = f"{m[:4]}-{m[4:].lower()}"
    assert [f[0] for f in descargar(api, auth, "/vehiculos/exportar", buscar=buscado)[1:]] == [m]
    # Por marca: los mismos que la búsqueda de la pantalla.
    marca = con_taller["marca"]
    esperados = [v["matricula"] for v in todos if marca.lower() in f"{v['matricula']}{v['marca']}{v['modelo']}".lower()]
    assert [f[0] for f in descargar(api, auth, "/vehiculos/exportar", buscar=marca)[1:]] == esperados


def test_vehiculos_con_textos_legibles(api: TestClient, auth: dict) -> None:
    filas = descargar(api, auth, "/vehiculos/exportar", estado="en_taller")
    fila = dict(zip(filas[0], filas[1], strict=True))

    assert fila["Estado"] == "En taller"  # no "en_taller"
    assert fila["Tipo"] in {"Autobús", "Microbús", "Furgoneta", "Camión", "Cisterna"}  # nombre, no id
    assert isinstance(fila["Km"], int)  # número de verdad, para poder sumar en Excel
    assert fila["Activo"] == "Sí"


# --- Personal ----------------------------------------------------------------


def test_personal_con_los_filtros_y_el_orden_de_la_pantalla(api: TestClient, auth: dict) -> None:
    personas = listar(api, auth, "/personas", puesto="conductor")
    en_rojo = [p["nombre"] for p in personas if p["semaforo"] == "rojo"]

    filas = descargar(api, auth, "/personas/exportar", puesto="conductor")
    assert len(filas) == 1 + len(personas)
    assert [f[0] for f in filas[1 : 1 + len(en_rojo)]] == sorted(en_rojo)  # primero los que están en rojo
    assert {f[1] for f in filas[1:]} == {"Conductor/a"}

    filas = descargar(api, auth, "/personas/exportar", semaforo="rojo")
    assert {f[4] for f in filas[1:]} == {"Caducada"}

    nombre = personas[0]["nombre"]
    assert [f[0] for f in descargar(api, auth, "/personas/exportar", buscar=nombre.split()[0].upper())[1:]] == [
        p["nombre"] for p in sorted(listar(api, auth, "/personas"), key=lambda p: ({"rojo": 0, "ambar": 1, "verde": 2}[p["semaforo"]], p["nombre"]))
        if nombre.split()[0].lower() in p["nombre"].lower()
    ]


def test_personal_las_fechas_son_fechas(api: TestClient, auth: dict) -> None:
    fila = descargar(api, auth, "/personas/exportar")[1]

    assert isinstance(fila[3], datetime)  # Excel guarda las fechas como fecha (con formato dd/mm/aaaa)


# --- Averías, OT, previsión, recambios y costes ------------------------------


@pytest.mark.parametrize("filtros", [{}, {"abiertas": False}, {"gravedad": "leve", "abiertas": False}])
def test_averias(api: TestClient, auth: dict, filtros: dict) -> None:
    filas = descargar(api, auth, "/averias/exportar", **filtros)

    assert [f[2] for f in filas[1:]] == [a["descripcion"] for a in listar(api, auth, "/averias", **filtros)]


def test_las_horas_salen_en_hora_de_espana(api: TestClient, auth: dict) -> None:
    """La BD guarda UTC; en el Excel se ve la hora local, como en la aplicación."""
    averia = listar(api, auth, "/averias")[0]
    utc = datetime.fromisoformat(averia["comunicada_en"])

    comunicada = descargar(api, auth, "/averias/exportar")[1][0]
    assert comunicada == utc.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Madrid")).replace(tzinfo=None)


@pytest.mark.parametrize("filtros", [{}, {"tipo": "preventiva"}, {"abiertas": True}])
def test_ordenes_de_trabajo(api: TestClient, auth: dict, filtros: dict) -> None:
    filas = descargar(api, auth, "/ordenes-trabajo/exportar", **filtros)
    ordenes = listar(api, auth, "/ordenes-trabajo", **filtros)

    assert [f[0] for f in filas[1:]] == [o["id"] for o in ordenes]
    assert sum(f[-1] for f in filas[1:]) == pytest.approx(sum(o["coste"]["total"] for o in ordenes))


def test_el_tablero_de_taller_se_exporta_tal_como_se_ve(api: TestClient, auth: dict) -> None:
    """Abiertas + cerradas en los últimos 30 días: las tres columnas del tablero."""
    hace_30 = str(HOY - timedelta(days=30))
    abiertas = listar(api, auth, "/ordenes-trabajo", abiertas=True)
    cerradas = listar(api, auth, "/ordenes-trabajo", cerradas_desde=hace_30)

    filas = descargar(api, auth, "/ordenes-trabajo/exportar", abiertas=True, cerradas_desde=hace_30)
    assert sorted(f[0] for f in filas[1:]) == sorted(o["id"] for o in abiertas + cerradas)
    assert len(abiertas) == 2 and cerradas


def test_prevision(api: TestClient, auth: dict) -> None:
    tipo, _ = ids_tipo_y_centro(api, auth)
    for filtros in ({}, {"tipo_id": tipo}):
        filas = descargar(api, auth, "/preventivos/prevision/exportar", **filtros)
        esperado = [(p["matricula"], p["plan_nombre"]) for p in listar(api, auth, "/preventivos/prevision", **filtros)]
        assert [(f[0], f[1]) for f in filas[1:]] == esperado


def test_recambios(api: TestClient, auth: dict) -> None:
    filas = descargar(api, auth, "/recambios/exportar", buscar="filtro")

    assert [f[0] for f in filas[1:]] == [r["referencia"] for r in listar(api, auth, "/recambios", buscar="filtro")]
    assert len(filas) == 1 + 3  # filtros de aceite, aire y combustible


def test_costes_por_vehiculo_del_panel(api: TestClient, auth: dict) -> None:
    tipo, _ = ids_tipo_y_centro(api, auth)
    datos = listar(api, auth, "/panel/indicadores", tipo_id=tipo)

    filas = descargar(api, auth, "/panel/indicadores/exportar", tipo_id=tipo)
    assert [(f[0], f[1]) for f in filas[1:]] == [(v["matricula"], v["coste"]) for v in datos["vehiculos"]]


# --- Seguridad y aislamiento -------------------------------------------------


def test_un_texto_que_empieza_por_igual_no_se_convierte_en_formula(api: TestClient, auth: dict) -> None:
    """Inyección de fórmulas: lo que escribe un usuario nunca se ejecuta al abrir el Excel."""
    vehiculo = listar(api, auth, "/vehiculos")[0]
    peligro = '=HYPERLINK("http://ejemplo.invalid","pulsa")'
    api.post("/averias", data={"vehiculo_id": str(vehiculo["id"]), "descripcion": peligro, "gravedad": "leve"}, headers=auth)

    r = api.get("/averias/exportar", headers=auth)
    hoja = load_workbook(BytesIO(r.content)).active
    celda = next(c for c in hoja["C"] if c.value == peligro)
    assert celda.data_type == "s"  # texto, no fórmula ("f")


def test_nombre_del_archivo(api: TestClient, auth: dict) -> None:
    r = api.get("/vehiculos/exportar", headers=auth)

    assert r.headers["content-disposition"] == f'attachment; filename="vehiculos-{HOY.isoformat()}.xlsx"'


def test_cada_empresa_exporta_solo_lo_suyo(api: TestClient, db: Session, auth: dict) -> None:
    otra = cabeceras(crear_usuario(db, crear_empresa(db, "Otra"), "x@otra.example.com", RolUsuario.CONDUCTOR))

    for ruta in ("/vehiculos/exportar", "/personas/exportar", "/averias/exportar", "/ordenes-trabajo/exportar", "/recambios/exportar"):
        assert len(descargar(api, otra, ruta)) == 1, ruta  # solo la cabecera


def test_sin_sesion_no_se_exporta(api: TestClient) -> None:
    assert api.get("/vehiculos/exportar").status_code == 401
