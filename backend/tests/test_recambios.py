"""Catálogo de recambios (MAN-09).

Criterio: "Al añadir un recambio a una OT se rellena su precio por defecto."
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LineaOT, RolUsuario
from tests.fabricas import cabeceras, crear_empresa, crear_usuario
from tests.test_ordenes_api import e, ot_manual, taller  # noqa: F401 (e es un fixture)


def crear_recambio(api: TestClient, e: dict, referencia: str = "FIL-ACE-210", nombre: str = "Filtro de aceite", precio: Any = "20.00") -> Any:
    return api.post("/recambios", json={"referencia": referencia, "nombre": nombre, "precio": precio}, headers=taller(e))


def anadir_recambio(api: TestClient, e: dict, ot: dict, recambio_id: int, **extra: Any) -> Any:
    linea = {"concepto": "recambio", "recambio_id": recambio_id, "cantidad": 2, **extra}
    return api.post(f"/ordenes-trabajo/{ot['id']}/lineas", json=linea, headers=taller(e))


# --- MAN-09: precio por defecto ----------------------------------------------


def test_al_anadir_un_recambio_a_una_ot_se_rellena_su_precio(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-09."""
    recambio = crear_recambio(api, e).json()

    r = anadir_recambio(api, e, ot_manual(api, e), recambio["id"])

    assert r.status_code == 201, r.text
    linea = r.json()["lineas"][-1]
    assert linea["precio_unitario"] == 20.0  # el del catálogo
    assert linea["descripcion"] == "Filtro de aceite (FIL-ACE-210)"
    assert linea["recambio_id"] == recambio["id"]
    assert linea["importe"] == 40.0  # 2 × 20,00
    assert r.json()["coste"]["recambios"] == 40.0


def test_el_precio_se_puede_ajustar_en_la_ot(api: TestClient, e: dict) -> None:
    """El del catálogo es el precio POR DEFECTO: si se envía otro, manda el enviado."""
    recambio = crear_recambio(api, e).json()

    r = anadir_recambio(api, e, ot_manual(api, e), recambio["id"], precio_unitario="17.50", descripcion="Filtro (oferta)")

    linea = r.json()["lineas"][-1]
    assert (linea["precio_unitario"], linea["descripcion"]) == (17.5, "Filtro (oferta)")


def test_cambiar_el_precio_del_catalogo_no_altera_las_ot_ya_registradas(api: TestClient, e: dict) -> None:
    recambio = crear_recambio(api, e).json()
    ot = ot_manual(api, e)
    anadir_recambio(api, e, ot, recambio["id"])

    api.patch(f"/recambios/{recambio['id']}", json={"precio": "25.00"}, headers=taller(e))

    assert api.get(f"/ordenes-trabajo/{ot['id']}", headers=taller(e)).json()["coste"]["total"] == 40.0
    nueva = anadir_recambio(api, e, ot_manual(api, e), recambio["id"]).json()
    assert nueva["lineas"][-1]["precio_unitario"] == 25.0  # las nuevas sí usan el precio nuevo


def test_sin_catalogo_siguen_valiendo_los_recambios_sueltos(api: TestClient, e: dict) -> None:
    linea = {"concepto": "recambio", "descripcion": "Tornillería", "cantidad": 1, "precio_unitario": "3.20"}

    r = api.post(f"/ordenes-trabajo/{ot_manual(api, e)['id']}/lineas", json=linea, headers=taller(e))

    assert r.status_code == 201
    assert r.json()["lineas"][-1]["recambio_id"] is None


@pytest.mark.parametrize(
    "linea",
    [
        {"concepto": "recambio", "descripcion": "Sin precio", "cantidad": 1},  # sin catálogo hace falta precio
        {"concepto": "recambio", "precio_unitario": 5, "cantidad": 1},  # … y descripción
        {"concepto": "mano_obra", "recambio_id": 1, "cantidad": 1},  # el catálogo solo en líneas de recambio
    ],
)
def test_lineas_incompletas(api: TestClient, e: dict, linea: dict) -> None:
    assert api.post(f"/ordenes-trabajo/{ot_manual(api, e)['id']}/lineas", json=linea, headers=taller(e)).status_code == 422


def test_un_recambio_dado_de_baja_o_de_otra_empresa_no_se_puede_usar(api: TestClient, e: dict, db: Session) -> None:
    de_baja = crear_recambio(api, e).json()
    api.delete(f"/recambios/{de_baja['id']}", headers=taller(e))
    otra = crear_empresa(db, "Otra")
    ajeno = api.post(
        "/recambios",
        json={"referencia": "X1", "nombre": "Ajeno", "precio": 1},
        headers=cabeceras(crear_usuario(db, otra, "t@otra.example.com", RolUsuario.TALLER)),
    ).json()
    ot = ot_manual(api, e)

    assert anadir_recambio(api, e, ot, de_baja["id"]).status_code == 422
    assert anadir_recambio(api, e, ot, ajeno["id"]).status_code == 422


def test_la_bd_impide_enlazar_un_recambio_en_una_linea_que_no_es_de_recambio(api: TestClient, e: dict, db: Session) -> None:
    recambio = crear_recambio(api, e).json()
    ot = ot_manual(api, e)
    anadir_recambio(api, e, ot, recambio["id"])
    linea = db.scalar(select(LineaOT).where(LineaOT.ot_id == ot["id"]))

    linea.concepto = "mano_obra"
    with pytest.raises(IntegrityError):
        db.flush()


# --- Catálogo: alta, edición, baja, búsqueda, permisos ----------------------


def test_la_referencia_se_guarda_en_mayusculas_y_no_se_repite(api: TestClient, e: dict) -> None:
    assert crear_recambio(api, e, referencia="  fil-ace-210 ").json()["referencia"] == "FIL-ACE-210"

    r = crear_recambio(api, e, referencia="FIL-ACE-210", nombre="Otro")
    assert r.status_code == 409


def test_editar_la_referencia_a_una_que_ya_existe_es_409(api: TestClient, e: dict) -> None:
    crear_recambio(api, e, referencia="A1")
    b = crear_recambio(api, e, referencia="B2").json()

    assert api.patch(f"/recambios/{b['id']}", json={"referencia": "a1"}, headers=taller(e)).status_code == 409
    assert api.patch(f"/recambios/{b['id']}", json={"nombre": None}, headers=taller(e)).status_code == 422


@pytest.mark.parametrize("precio", [-1, "1.234", "abc"])
def test_precio_invalido(api: TestClient, e: dict, precio: Any) -> None:
    assert crear_recambio(api, e, precio=precio).status_code == 422


def test_buscar_por_referencia_o_nombre_y_bajas(api: TestClient, e: dict) -> None:
    crear_recambio(api, e, referencia="FIL-ACE-210", nombre="Filtro de aceite")
    crear_recambio(api, e, referencia="NEU-315", nombre="Neumático")
    baja = crear_recambio(api, e, referencia="OLD-1", nombre="Filtro antiguo").json()
    api.delete(f"/recambios/{baja['id']}", headers=taller(e))
    conductor = e[RolUsuario.CONDUCTOR]  # consultar: cualquier rol

    def refs(**filtros: Any) -> list[str]:
        return [r["referencia"] for r in api.get("/recambios", params=filtros, headers=conductor).json()]

    assert refs() == ["FIL-ACE-210", "NEU-315"]  # ordenados por nombre
    assert refs(buscar="filtro") == ["FIL-ACE-210"]
    assert refs(buscar="neu") == ["NEU-315"]
    assert refs(buscar="filtro", incluir_bajas=True) == ["OLD-1", "FIL-ACE-210"]  # "Filtro antiguo" < "Filtro de…"


@pytest.mark.parametrize("rol", [RolUsuario.TRAFICO, RolUsuario.CONDUCTOR])
def test_solo_gerente_y_taller_gestionan_el_catalogo(api: TestClient, e: dict, rol: RolUsuario) -> None:
    recambio = crear_recambio(api, e).json()

    assert api.post("/recambios", json={"referencia": "Z", "nombre": "Z", "precio": 1}, headers=e[rol]).status_code == 403
    assert api.patch(f"/recambios/{recambio['id']}", json={"precio": 1}, headers=e[rol]).status_code == 403
    assert api.delete(f"/recambios/{recambio['id']}", headers=e[rol]).status_code == 403
    assert api.post("/recambios", json={"referencia": "Z", "nombre": "Z", "precio": 1}, headers=e[RolUsuario.ADMIN]).status_code == 201


def test_cada_empresa_ve_solo_su_catalogo(api: TestClient, e: dict, db: Session) -> None:
    recambio = crear_recambio(api, e).json()
    otra = cabeceras(crear_usuario(db, crear_empresa(db, "Otra"), "t@otra.example.com", RolUsuario.TALLER))

    assert api.get("/recambios", headers=otra).json() == []
    assert api.patch(f"/recambios/{recambio['id']}", json={"precio": 1}, headers=otra).status_code == 404
    # Otra empresa puede usar la misma referencia.
    assert api.post("/recambios", json={"referencia": "FIL-ACE-210", "nombre": "F", "precio": 1}, headers=otra).status_code == 201
