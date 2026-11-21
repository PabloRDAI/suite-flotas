"""Tests de la empresa de demostración (GEN-04)."""

from collections import Counter
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings

from app.models import Asignacion, Centro, Empresa, EstadoPlan, LecturaKm, Persona, RolUsuario, Usuario, Vehiculo
from app.reglas.asignaciones import AsignacionExistente, Periodo, comprobar_habitual
from app.reglas.km import Lectura, comprobar_lectura
from app.servicios.demo import (
    PASSWORD_DEMO,
    PLANES_DEMO,
    TIPOS_VEHICULO,
    DemoYaExiste,
    crear_empresa_demo,
    email_demo,
    planificar_asignaciones,
    planificar_demo,
    planificar_personal,
    planificar_preventivos,
)
from tests.fabricas import crear_empresa, crear_usuario

HOY = date(2026, 11, 21)


def contar(db: Session, modelo: type, empresa_id: int) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(modelo.empresa_id == empresa_id)) or 0


# --- El plan (Python puro, sin BD) -------------------------------------------


def test_el_plan_es_siempre_el_mismo() -> None:
    """Semilla fija: dos ejecuciones generan exactamente los mismos datos."""
    assert planificar_demo(HOY) == planificar_demo(HOY)


def test_otra_semilla_da_otros_datos() -> None:
    assert planificar_demo(HOY, semilla=1) != planificar_demo(HOY, semilla=2)


def test_el_plan_tiene_25_vehiculos_con_matricula_unica() -> None:
    plan = planificar_demo(HOY)

    assert len(plan) == 25
    assert len({v.matricula for v in plan}) == 25


def test_las_lecturas_cumplen_la_regla_de_km() -> None:
    """Los datos demo respetan FLO-05: cada lectura pasaría la validación de la API."""
    for v in planificar_demo(HOY):
        anteriores: list[Lectura] = []
        for fecha, km in v.lecturas:
            nueva = Lectura(fecha, km)
            comprobar_lectura(nueva, anteriores, HOY)  # lanza excepción si no vale
            anteriores.append(nueva)
        assert v.lecturas[0][0] < v.lecturas[-1][0] <= HOY
        assert (v.lecturas[-1][0] - v.lecturas[0][0]).days >= 175  # ~6 meses de historial


# --- Guardado en la BD -------------------------------------------------------


def test_crea_lo_que_pide_la_spec(db: Session) -> None:
    """GEN-04 (parte disponible hoy): 1 empresa, 2 centros y 25 vehículos con historial."""
    r = crear_empresa_demo(db, hoy=HOY)

    assert db.get(Empresa, r.empresa_id) is not None
    assert contar(db, Centro, r.empresa_id) == 2
    assert contar(db, Vehiculo, r.empresa_id) == 25
    assert contar(db, LecturaKm, r.empresa_id) == r.lecturas_km > 25 * 20
    assert r.vehiculos == 25


def test_un_usuario_de_cada_rol(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    roles = set(db.scalars(select(Usuario.rol).where(Usuario.empresa_id == r.empresa_id)))

    assert roles == set(RolUsuario)


def test_km_actuales_son_los_de_la_ultima_lectura(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    for vehiculo in db.scalars(select(Vehiculo).where(Vehiculo.empresa_id == r.empresa_id)):
        ultima = db.scalar(select(func.max(LecturaKm.km)).where(LecturaKm.vehiculo_id == vehiculo.id))
        assert vehiculo.km_actuales == ultima


def test_hay_casos_para_enseñar_en_el_panel(db: Session) -> None:
    """3 no aptos (ITV caducada, seguro caducado e inmovilizado por avería) y 3 en ámbar."""
    r = crear_empresa_demo(db, hoy=HOY)

    assert len(r.no_aptos) == 3
    assert len(r.en_ambar) == 3


def test_los_no_aptos_coinciden_con_la_api(api: TestClient, db: Session) -> None:
    """El resumen del script y el endpoint /aptitud aplican las mismas reglas."""
    r = crear_empresa_demo(db, hoy=date.today())
    login = api.post("/auth/login", json={"email": email_demo("trafico"), "password": PASSWORD_DEMO})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    no_aptos = [
        v["matricula"]
        for v in api.get("/vehiculos", headers=auth).json()
        if not api.get(f"/vehiculos/{v['id']}/aptitud", headers=auth).json()["apto"]
    ]

    assert sorted(no_aptos) == sorted(r.no_aptos)


def test_se_puede_hacer_login_con_los_usuarios_demo(api: TestClient, db: Session) -> None:
    crear_empresa_demo(db, hoy=HOY)

    for alias in ("admin", "trafico", "taller", "conductor"):
        respuesta = api.post("/auth/login", json={"email": email_demo(alias), "password": PASSWORD_DEMO})
        assert respuesta.status_code == 200, alias


# --- Personal (PER-01, PER-02) -----------------------------------------------


def test_el_plan_de_personal_tiene_30_personas_con_nombre_unico() -> None:
    plan = planificar_personal(HOY)

    assert len(plan) == 30
    assert len({p.nombre for p in plan}) == 30
    assert Counter(p.puesto for p in plan) == {"conductor": 20, "mecanico": 5, "trafico": 3, "otro": 2}


def test_crea_las_30_personas_con_su_documentacion(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    assert contar(db, Persona, r.empresa_id) == r.personas == 30
    assert len(r.personas_en_rojo) == 1  # CAP caducado
    assert len(r.personas_en_ambar) == 2


def test_los_usuarios_demo_estan_enlazados_a_su_persona(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    enlaces = db.execute(
        select(Usuario.rol, Persona.puesto)
        .join(Persona, Persona.usuario_id == Usuario.id)
        .where(Usuario.empresa_id == r.empresa_id)
    ).all()

    assert dict(enlaces) == {"admin": "otro", "trafico": "trafico", "taller": "mecanico", "conductor": "conductor"}


# --- Asignaciones (PER-03, PER-04) -------------------------------------------


def test_el_plan_de_asignaciones_cumple_un_habitual_a_la_vez() -> None:
    """Se comprueba con la MISMA regla que usa la API (comprobar_habitual)."""
    personal = planificar_personal(HOY)
    plan = planificar_asignaciones(HOY, personal)
    ya_vistas: dict[int, list[AsignacionExistente]] = {}
    for a in plan:
        periodo = Periodo(a.desde, a.hasta)
        comprobar_habitual(periodo, a.habitual, ya_vistas.get(a.vehiculo, []))  # lanza excepción si no vale
        ya_vistas.setdefault(a.vehiculo, []).append(AsignacionExistente("x", periodo, a.habitual))
        assert personal[a.persona].puesto == "conductor"


def test_crea_las_asignaciones_con_historial_y_aviso(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    assert contar(db, Asignacion, r.empresa_id) == r.asignaciones == 27  # 20 habituales + 5 anteriores + 2 temporales
    terminadas = db.scalar(
        select(func.count()).select_from(Asignacion).where(Asignacion.empresa_id == r.empresa_id, Asignacion.hasta < HOY)
    )
    assert terminadas == 6  # las 5 habituales anteriores + la temporal pasada
    assert len(r.asignaciones_con_aviso) == 1  # la conductora con el CAP caducado


# --- Preventivos (MAN-01) ----------------------------------------------------


def test_los_estados_de_los_preventivos_son_coherentes() -> None:
    """Ninguna realización futura ni con más km de los que tiene el vehículo."""
    vehiculos = planificar_demo(HOY)
    for p in planificar_preventivos(HOY, vehiculos):
        assert p.ultima_fecha <= HOY
        assert 0 <= p.ultimos_km <= vehiculos[p.vehiculo].lecturas[-1][1]


def test_crea_los_planes_con_casos_vencidos_y_proximos(db: Session) -> None:
    r = crear_empresa_demo(db, hoy=HOY)

    assert r.planes == sum(len(planes) for planes in PLANES_DEMO.values()) == 9
    assert len(r.preventivos_vencidos) == 2
    assert any("Vencido por km" in v for v in r.preventivos_vencidos)
    assert any("Vencido por fecha" in v for v in r.preventivos_vencidos)
    assert len(r.preventivos_proximos) == 2
    # Cada vehículo tiene el estado de todos los planes de su tipo.
    assert contar(db, EstadoPlan, r.empresa_id) == sum(len(PLANES_DEMO[v.tipo]) for v in planificar_demo(HOY))


# --- Realismo de los datos ---------------------------------------------------


def test_los_km_son_coherentes_con_la_antiguedad() -> None:
    """Ningún vehículo puede tener más km de los que daría haber rodado a diario desde su año."""
    km_por_dia = {nombre: km for nombre, _, km in TIPOS_VEHICULO}
    for v in planificar_demo(HOY):
        fecha_inicio, km_inicio = v.lecturas[0]
        dias_en_servicio = (fecha_inicio - date(v.anio, 1, 1)).days
        assert v.anio < HOY.year, f"{v.matricula}: no debería ser de este año"
        assert km_inicio <= dias_en_servicio * km_por_dia[v.tipo], f"{v.matricula}: {km_inicio} km es demasiado"


# --- Repetir la ejecución ----------------------------------------------------


def test_sin_reiniciar_no_se_duplica(db: Session) -> None:
    crear_empresa_demo(db, hoy=HOY)

    with pytest.raises(DemoYaExiste):
        crear_empresa_demo(db, hoy=HOY)


def test_reiniciar_recrea_la_demo_sin_tocar_otras_empresas(db: Session) -> None:
    otra = crear_empresa(db, "Empresa real que no se debe tocar")
    crear_usuario(db, otra, "gerente@example.com")
    primera = crear_empresa_demo(db, hoy=HOY)

    segunda = crear_empresa_demo(db, hoy=HOY, reiniciar=True)

    assert segunda.empresa_id != primera.empresa_id
    assert db.get(Empresa, primera.empresa_id) is None  # la demo anterior se borró entera
    assert db.get(Empresa, otra.id) is not None  # la otra empresa sigue intacta
    assert contar(db, Usuario, otra.id) == 1
    assert db.scalar(select(func.count()).select_from(Empresa).where(Empresa.nombre.like("%Demo%"))) == 1


def test_reiniciar_borra_tambien_las_fotos_de_las_averias(api: TestClient, db: Session) -> None:
    """Al borrar la empresa demo no deben quedar fotos huérfanas en el disco."""
    crear_empresa_demo(db, hoy=HOY)
    login = api.post("/auth/login", json={"email": email_demo("conductor"), "password": PASSWORD_DEMO}).json()
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    vehiculo = api.get("/vehiculos", headers=auth).json()[0]
    antes = set(get_settings().carpeta_adjuntos.glob("*"))
    api.post(
        "/averias",
        data={"vehiculo_id": str(vehiculo["id"]), "descripcion": "Prueba con foto", "gravedad": "leve"},
        files={"foto": ("f.png", b"\x89PNG\r\n\x1a\n" + bytes(16), "image/png")},
        headers=auth,
    )
    (foto,) = set(get_settings().carpeta_adjuntos.glob("*")) - antes

    crear_empresa_demo(db, hoy=HOY, reiniciar=True)

    assert not foto.exists()

