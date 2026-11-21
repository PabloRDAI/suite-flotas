"""Tests de permisos por rol (GEN-02) y de aislamiento entre empresas (GEN-01).

Son los criterios de aceptación de la spec:
- GEN-01: "Un usuario de la empresa A nunca ve datos de la empresa B".
- GEN-02: "Un conductor recibe 403 al intentar borrar un vehículo".
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import EstadoVehiculo, RolUsuario
from tests.fabricas import cabeceras, crear_empresa, crear_usuario, crear_vehiculo

# --- GEN-02: permisos por rol ------------------------------------------------


def test_un_conductor_recibe_403_al_intentar_borrar_un_vehiculo(api: TestClient, db: Session) -> None:
    """Criterio de aceptación literal de GEN-02."""
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa)
    conductor = crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR)

    respuesta = api.delete(f"/vehiculos/{vehiculo.id}", headers=cabeceras(conductor))

    assert respuesta.status_code == 403
    db.refresh(vehiculo)
    assert vehiculo.activo is True  # y el vehículo sigue intacto


@pytest.mark.parametrize(
    ("rol", "codigo_esperado"),
    [
        (RolUsuario.ADMIN, 204),
        (RolUsuario.TRAFICO, 204),
        (RolUsuario.TALLER, 403),
        (RolUsuario.CONDUCTOR, 403),
    ],
)
def test_quien_puede_dar_de_baja_un_vehiculo(
    api: TestClient, db: Session, rol: RolUsuario, codigo_esperado: int
) -> None:
    """Matriz de permisos: el mismo test se ejecuta una vez por cada rol."""
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa)
    usuario = crear_usuario(db, empresa, f"{rol}@example.com", rol)

    respuesta = api.delete(f"/vehiculos/{vehiculo.id}", headers=cabeceras(usuario))

    assert respuesta.status_code == codigo_esperado


def test_la_baja_es_logica(api: TestClient, db: Session) -> None:
    """FLO-01: dar de baja no borra la fila; la marca como inactiva y "de baja"."""
    empresa = crear_empresa(db)
    vehiculo = crear_vehiculo(db, empresa)
    admin = crear_usuario(db, empresa)

    api.delete(f"/vehiculos/{vehiculo.id}", headers=cabeceras(admin))

    db.refresh(vehiculo)
    assert vehiculo.activo is False
    assert vehiculo.estado == EstadoVehiculo.BAJA
    # Ya no aparece en el listado...
    assert api.get("/vehiculos", headers=cabeceras(admin)).json() == []
    # ...y darlo de baja otra vez responde 404.
    assert api.delete(f"/vehiculos/{vehiculo.id}", headers=cabeceras(admin)).status_code == 404


def test_cualquier_rol_puede_listar_vehiculos(api: TestClient, db: Session) -> None:
    empresa = crear_empresa(db)
    crear_vehiculo(db, empresa)
    conductor = crear_usuario(db, empresa, "conductor@example.com", RolUsuario.CONDUCTOR)

    assert api.get("/vehiculos", headers=cabeceras(conductor)).status_code == 200


def test_sin_sesion_no_se_accede_a_los_vehiculos(api: TestClient) -> None:
    assert api.get("/vehiculos").status_code == 401
    assert api.delete("/vehiculos/1").status_code == 401


# --- GEN-01: aislamiento entre empresas --------------------------------------


def test_un_usuario_solo_ve_los_vehiculos_de_su_empresa(api: TestClient, db: Session) -> None:
    """Criterio de aceptación literal de GEN-01."""
    empresa_a = crear_empresa(db, "Empresa A")
    empresa_b = crear_empresa(db, "Empresa B")
    crear_vehiculo(db, empresa_a, "1111AAA")
    crear_vehiculo(db, empresa_b, "2222BBB")
    usuario_a = crear_usuario(db, empresa_a, "a@example.com")

    matriculas = [v["matricula"] for v in api.get("/vehiculos", headers=cabeceras(usuario_a)).json()]

    assert matriculas == ["1111AAA"]


def test_no_se_puede_dar_de_baja_un_vehiculo_de_otra_empresa(api: TestClient, db: Session) -> None:
    """Un admin de A no puede tocar un vehículo de B; recibe 404 (no se revela que existe)."""
    empresa_a = crear_empresa(db, "Empresa A")
    empresa_b = crear_empresa(db, "Empresa B")
    vehiculo_de_b = crear_vehiculo(db, empresa_b)
    admin_a = crear_usuario(db, empresa_a, "admin-a@example.com")

    respuesta = api.delete(f"/vehiculos/{vehiculo_de_b.id}", headers=cabeceras(admin_a))

    assert respuesta.status_code == 404
    db.refresh(vehiculo_de_b)
    assert vehiculo_de_b.activo is True
