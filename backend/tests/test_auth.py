"""Tests del login y de la identificación por token (GEN-02)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import RolUsuario
from app.seguridad import crear_token
from tests.fabricas import cabeceras, crear_empresa, crear_usuario

PASSWORD = "contraseña-de-prueba-larga"


def test_login_correcto_devuelve_un_token_que_identifica_al_usuario(api: TestClient, db: Session) -> None:
    empresa = crear_empresa(db)
    crear_usuario(db, empresa, "ana@example.com", RolUsuario.TRAFICO, password=PASSWORD)

    respuesta = api.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})

    assert respuesta.status_code == 200
    token = respuesta.json()["access_token"]
    assert respuesta.json()["token_type"] == "bearer"

    yo = api.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert yo.status_code == 200
    assert yo.json()["email"] == "ana@example.com"
    assert yo.json()["rol"] == "trafico"
    assert yo.json()["empresa_id"] == empresa.id
    assert "hash_password" not in yo.json()  # nunca se expone el hash


def test_el_email_no_distingue_mayusculas(api: TestClient, db: Session) -> None:
    crear_usuario(db, crear_empresa(db), "ana@example.com", password=PASSWORD)

    respuesta = api.post("/auth/login", json={"email": "ANA@Example.COM", "password": PASSWORD})

    assert respuesta.status_code == 200


def test_contrasena_incorrecta_y_email_inexistente_dan_el_mismo_error(api: TestClient, db: Session) -> None:
    """Mismo código y mismo mensaje: no se puede averiguar qué emails existen."""
    crear_usuario(db, crear_empresa(db), "ana@example.com", password=PASSWORD)

    mala_password = api.post("/auth/login", json={"email": "ana@example.com", "password": "otra"})
    email_inexistente = api.post("/auth/login", json={"email": "nadie@example.com", "password": PASSWORD})

    assert mala_password.status_code == email_inexistente.status_code == 401
    assert mala_password.json() == email_inexistente.json()


def test_un_usuario_desactivado_no_puede_entrar(api: TestClient, db: Session) -> None:
    crear_usuario(db, crear_empresa(db), "baja@example.com", password=PASSWORD, activo=False)

    respuesta = api.post("/auth/login", json={"email": "baja@example.com", "password": PASSWORD})

    assert respuesta.status_code == 401


def test_desactivar_un_usuario_invalida_sus_tokens_al_momento(api: TestClient, db: Session) -> None:
    usuario = crear_usuario(db, crear_empresa(db))
    token = cabeceras(usuario)
    assert api.get("/auth/yo", headers=token).status_code == 200

    usuario.activo = False
    db.flush()

    assert api.get("/auth/yo", headers=token).status_code == 401


def test_sin_token_responde_401(api: TestClient) -> None:
    respuesta = api.get("/auth/yo")

    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_token_falso_o_caducado_responde_401(api: TestClient, db: Session) -> None:
    usuario = crear_usuario(db, crear_empresa(db))

    falso = api.get("/auth/yo", headers={"Authorization": "Bearer esto.no.vale"})
    caducado = api.get("/auth/yo", headers={"Authorization": f"Bearer {crear_token(usuario.id, minutos=-1)}"})

    assert falso.status_code == 401
    assert caducado.status_code == 401


def test_email_con_formato_incorrecto_responde_422(api: TestClient) -> None:
    """422 = la petición tiene datos inválidos (lo valida Pydantic antes del endpoint)."""
    respuesta = api.post("/auth/login", json={"email": "no-es-un-email", "password": "x"})

    assert respuesta.status_code == 422
