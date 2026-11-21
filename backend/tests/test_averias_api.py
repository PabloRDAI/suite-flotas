"""Tests de averías por la API (MAN-03) y su efecto en el estado del vehículo (FLO-03).

Criterio de MAN-03: "Una avería que 'inmoviliza' cambia el estado del vehículo al instante."
"""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asignacion, Centro, Puesto, RolUsuario
from tests.fabricas import cabeceras, crear_empresa, crear_persona, crear_usuario, crear_vehiculo

# Imágenes mínimas: lo que importa es su "firma" (los primeros bytes).
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa, "1111AAA")
    usuarios = {rol: crear_usuario(db, empresa, f"{rol}@example.com", rol) for rol in RolUsuario}
    return {"db": db, "empresa": empresa, "vehiculo": vehiculo, "usuarios": usuarios,
            **{rol: cabeceras(u) for rol, u in usuarios.items()}}


def comunicar(api: TestClient, e: dict, gravedad: str = "inmoviliza", foto: tuple | None = None,
              rol: RolUsuario = RolUsuario.CONDUCTOR, **datos: Any) -> Any:
    campos = {"vehiculo_id": str(e["vehiculo"].id), "descripcion": "No arranca: fallo eléctrico", "gravedad": gravedad, **datos}
    archivos = {"foto": foto} if foto else None
    return api.post("/averias", data=campos, files=archivos, headers=e[rol])


def estado_vehiculo(api: TestClient, e: dict) -> str:
    return api.get(f"/vehiculos/{e['vehiculo'].id}", headers=e[RolUsuario.TRAFICO]).json()["estado"]


# --- MAN-03: efecto en el estado del vehículo --------------------------------


def test_una_averia_que_inmoviliza_cambia_el_estado_al_instante(api: TestClient, e: dict) -> None:
    """Criterio literal de MAN-03: la propia respuesta ya trae el estado nuevo."""
    r = comunicar(api, e, "inmoviliza")

    assert r.status_code == 201
    assert r.json()["estado_vehiculo"] == "inmovilizado"
    assert r.json()["estado"] == "comunicada"
    assert estado_vehiculo(api, e) == "inmovilizado"


def test_el_panel_lo_cuenta_como_inmovilizado_y_no_apto(api: TestClient, e: dict) -> None:
    comunicar(api, e, "inmoviliza")

    panel = api.get("/panel", headers=e[RolUsuario.TRAFICO]).json()

    assert panel["contadores"]["inmovilizado"] == 1
    assert panel["contadores"]["no_aptos"] == 1
    assert panel["vehiculos"][0]["motivos"] == ["Estado: inmovilizado"]
    assert panel["alertas"][0]["tipo"] == "averia"
    assert panel["alertas"][0]["semaforo"] == "rojo"
    assert panel["alertas"][0]["mensaje"] == "Avería (inmoviliza): No arranca: fallo eléctrico"


@pytest.mark.parametrize("gravedad", ["leve", "grave"])
def test_una_averia_leve_o_grave_no_inmoviliza(api: TestClient, e: dict, gravedad: str) -> None:
    r = comunicar(api, e, gravedad)

    assert r.json()["estado_vehiculo"] == "operativo"
    alerta = api.get("/panel", headers=e[RolUsuario.TRAFICO]).json()["alertas"][0]
    assert (alerta["tipo"], alerta["semaforo"]) == ("averia", "ambar")


def test_al_resolverla_vuelve_a_operativo(api: TestClient, e: dict) -> None:
    averia = comunicar(api, e, "inmoviliza").json()

    r = api.post(f"/averias/{averia['id']}/resolver", json={"nota": "Batería sustituida"}, headers=e[RolUsuario.TALLER])

    assert r.status_code == 200
    assert (r.json()["estado"], r.json()["estado_vehiculo"]) == ("resuelta", "operativo")
    assert r.json()["nota_resolucion"] == "Batería sustituida"
    assert r.json()["resuelta_en"] is not None
    assert estado_vehiculo(api, e) == "operativo"


def test_sigue_inmovilizado_mientras_quede_otra_que_inmoviliza(api: TestClient, e: dict) -> None:
    primera = comunicar(api, e, "inmoviliza").json()
    comunicar(api, e, "inmoviliza", descripcion="Fuga de aceite")

    r = api.post(f"/averias/{primera['id']}/resolver", json={}, headers=e[RolUsuario.TALLER])

    assert r.json()["estado_vehiculo"] == "inmovilizado"


def test_no_se_resuelve_dos_veces(api: TestClient, e: dict) -> None:
    averia = comunicar(api, e).json()
    api.post(f"/averias/{averia['id']}/resolver", json={}, headers=e[RolUsuario.TALLER])

    assert api.post(f"/averias/{averia['id']}/resolver", json={}, headers=e[RolUsuario.TALLER]).status_code == 409


# --- Foto opcional -----------------------------------------------------------


@pytest.mark.parametrize(("contenido", "tipo"), [(PNG, "image/png"), (JPEG, "image/jpeg")])
def test_con_foto_se_guarda_y_se_puede_ver(api: TestClient, e: dict, contenido: bytes, tipo: str) -> None:
    averia = comunicar(api, e, foto=("foto_del_movil.img", contenido, "application/octet-stream")).json()

    foto = api.get(f"/averias/{averia['id']}/foto", headers=e[RolUsuario.TALLER])

    assert averia["tiene_foto"] is True
    assert foto.status_code == 200
    assert foto.content == contenido
    assert foto.headers["content-type"] == tipo  # por su firma, no por el nombre ni lo que dijo el navegador


def test_la_foto_se_guarda_con_un_nombre_aleatorio_en_la_carpeta_de_adjuntos(api: TestClient, e: dict) -> None:
    antes = set(get_settings().carpeta_adjuntos.glob("*"))

    comunicar(api, e, foto=("../../malicioso.png", PNG, "image/png"))

    (nueva,) = set(get_settings().carpeta_adjuntos.glob("*")) - antes
    assert nueva.suffix == ".png"
    assert "malicioso" not in nueva.name
    assert len(nueva.stem) == 32  # uuid4 en hexadecimal


def test_un_archivo_que_no_es_imagen_se_rechaza_aunque_se_llame_jpg(api: TestClient, e: dict) -> None:
    r = comunicar(api, e, foto=("foto.jpg", b"#!/bin/sh\necho hola", "image/jpeg"))

    assert r.status_code == 422
    assert "JPEG, PNG o WebP" in r.json()["detail"]


def test_una_foto_demasiado_grande_se_rechaza(api: TestClient, e: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_foto_mb", 1)
    grande = PNG + b"\x00" * (1024 * 1024)

    r = comunicar(api, e, foto=("grande.png", grande, "image/png"))

    assert r.status_code == 413
    assert api.get("/averias", headers=e[RolUsuario.TALLER]).json() == []  # y no se guarda la avería


def test_tambien_se_admite_webp(api: TestClient, e: dict) -> None:
    """WebP, el formato que usan muchos móviles Android: firma "RIFF....WEBP"."""
    webp = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32

    averia = comunicar(api, e, foto=("foto.webp", webp, "image/webp")).json()

    foto = api.get(f"/averias/{averia['id']}/foto", headers=e[RolUsuario.TALLER])
    assert foto.headers["content-type"] == "image/webp"


def test_una_foto_vacia_se_rechaza(api: TestClient, e: dict) -> None:
    assert comunicar(api, e, foto=("vacia.png", b"", "image/png")).status_code == 422


def test_si_la_foto_desaparece_del_disco_responde_404(api: TestClient, e: dict) -> None:
    """Si alguien borra el archivo a mano, la API no falla: responde que no está."""
    antes = set(get_settings().carpeta_adjuntos.glob("*"))
    averia = comunicar(api, e, foto=("f.png", PNG, "image/png")).json()
    (archivo,) = set(get_settings().carpeta_adjuntos.glob("*")) - antes
    archivo.unlink()

    assert api.get(f"/averias/{averia['id']}/foto", headers=e[RolUsuario.TALLER]).status_code == 404


def test_sin_foto_no_hay_foto_que_ver(api: TestClient, e: dict) -> None:
    averia = comunicar(api, e).json()

    assert averia["tiene_foto"] is False
    assert api.get(f"/averias/{averia['id']}/foto", headers=e[RolUsuario.TALLER]).status_code == 404


# --- Validaciones ------------------------------------------------------------


@pytest.mark.parametrize(
    "cambio", [{"descripcion": "  "}, {"descripcion": "     "}, {"descripcion": "ab"}, {"gravedad": "catastrofica"}]
)
def test_datos_invalidos_responden_422(api: TestClient, e: dict, cambio: dict) -> None:
    gravedad = cambio.pop("gravedad", "leve")

    assert comunicar(api, e, gravedad, **cambio).status_code == 422


def test_no_se_comunica_sobre_un_vehiculo_de_baja_ni_de_otra_empresa(api: TestClient, e: dict) -> None:
    ajeno = crear_vehiculo(e["db"], crear_empresa(e["db"], "Otra"), "9999ZZZ")
    assert comunicar(api, e, vehiculo_id=str(ajeno.id)).status_code == 422

    api.delete(f"/vehiculos/{e['vehiculo'].id}", headers=e[RolUsuario.TRAFICO])
    assert comunicar(api, e).status_code == 422


# --- Permisos y aislamiento --------------------------------------------------


@pytest.mark.parametrize("rol", list(RolUsuario))
def test_cualquier_rol_puede_comunicar(api: TestClient, e: dict, rol: RolUsuario) -> None:
    r = comunicar(api, e, "leve", rol=rol)

    assert r.status_code == 201
    assert r.json()["comunicada_por"] == "Usuario de prueba"


@pytest.mark.parametrize(("rol", "codigo"), [(RolUsuario.ADMIN, 200), (RolUsuario.TALLER, 200), (RolUsuario.TRAFICO, 403), (RolUsuario.CONDUCTOR, 403)])
def test_quien_puede_resolver(api: TestClient, e: dict, rol: RolUsuario, codigo: int) -> None:
    averia = comunicar(api, e).json()

    assert api.post(f"/averias/{averia['id']}/resolver", json={}, headers=e[rol]).status_code == codigo


def test_cada_empresa_solo_ve_sus_averias(api: TestClient, e: dict) -> None:
    averia = comunicar(api, e, foto=("f.png", PNG, "image/png")).json()
    ajena = cabeceras(crear_usuario(e["db"], crear_empresa(e["db"], "Otra"), "x@example.com", RolUsuario.TALLER))

    assert api.get("/averias", headers=ajena).json() == []
    assert api.get(f"/averias/{averia['id']}", headers=ajena).status_code == 404
    assert api.get(f"/averias/{averia['id']}/foto", headers=ajena).status_code == 404
    assert api.post(f"/averias/{averia['id']}/resolver", json={}, headers=ajena).status_code == 404


# --- Listado -----------------------------------------------------------------


def test_listado_abiertas_por_defecto_y_filtros(api: TestClient, e: dict) -> None:
    leve = comunicar(api, e, "leve", descripcion="Retrovisor flojo").json()
    comunicar(api, e, "grave", descripcion="Ruido en la caja de cambios")
    api.post(f"/averias/{leve['id']}/resolver", json={}, headers=e[RolUsuario.TALLER])

    def descripciones(**filtros: Any) -> list[str]:
        return [a["descripcion"] for a in api.get("/averias", params=filtros, headers=e[RolUsuario.TALLER]).json()]

    assert descripciones() == ["Ruido en la caja de cambios"]  # la resuelta no sale
    assert descripciones(abiertas=False) == ["Ruido en la caja de cambios", "Retrovisor flojo"]  # más reciente primero
    assert descripciones(abiertas=False, gravedad="leve") == ["Retrovisor flojo"]
    otro = crear_vehiculo(e["db"], e["empresa"], "2222BBB")
    assert descripciones(vehiculo_id=otro.id) == []


# --- Vehículos sugeridos (para comunicar en menos de un minuto) ---------------


def test_al_conductor_se_le_sugiere_su_vehiculo_asignado(api: TestClient, e: dict) -> None:
    db = e["db"]
    otro = crear_vehiculo(db, e["empresa"], "2222BBB")
    persona = crear_persona(db, e["empresa"], "Ana", Puesto.CONDUCTOR, db.get(Centro, e["vehiculo"].centro_id))
    persona.usuario_id = e["usuarios"][RolUsuario.CONDUCTOR].id
    db.add_all([
        Asignacion(empresa_id=e["empresa"].id, persona_id=persona.id, vehiculo_id=otro.id, desde=date(2026, 1, 1), habitual=False),
        Asignacion(empresa_id=e["empresa"].id, persona_id=persona.id, vehiculo_id=e["vehiculo"].id, desde=date(2026, 1, 1), habitual=True),
    ])
    db.flush()

    sugeridos = api.get("/averias/vehiculos-sugeridos", headers=e[RolUsuario.CONDUCTOR]).json()

    assert [(v["matricula"], v["habitual"]) for v in sugeridos] == [("1111AAA", True), ("2222BBB", False)]


def test_sin_vehiculo_asignado_no_hay_sugerencias(api: TestClient, e: dict) -> None:
    assert api.get("/averias/vehiculos-sugeridos", headers=e[RolUsuario.TALLER]).json() == []
