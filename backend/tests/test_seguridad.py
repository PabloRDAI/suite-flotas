"""Tests unitarios de app/seguridad.py (no necesitan base de datos)."""

import jwt

from app.config import get_settings
from app.seguridad import ALGORITMO_JWT, crear_token, hash_password, leer_token, verificar_password


def test_el_hash_no_contiene_la_contrasena_y_es_argon2() -> None:
    h = hash_password("mi-contraseña-secreta")

    assert "mi-contraseña-secreta" not in h
    assert h.startswith("$argon2id$")


def test_la_misma_contrasena_da_hashes_distintos() -> None:
    """Cada hash lleva una "sal" aleatoria: no se pueden comparar hashes entre usuarios."""
    assert hash_password("igual") != hash_password("igual")


def test_verificar_password() -> None:
    h = hash_password("correcta")

    assert verificar_password("correcta", h)
    assert not verificar_password("incorrecta", h)
    assert not verificar_password("correcta", "esto-no-es-un-hash")


def test_token_valido_devuelve_el_usuario() -> None:
    assert leer_token(crear_token(42)) == 42


def test_token_caducado_no_vale() -> None:
    assert leer_token(crear_token(42, minutos=-1)) is None


def test_token_alterado_no_vale() -> None:
    token = crear_token(42)
    alterado = token[:-2] + ("AA" if not token.endswith("AA") else "BB")

    assert leer_token(alterado) is None


def test_token_firmado_con_otra_clave_no_vale() -> None:
    falso = jwt.encode({"sub": "42", "exp": 9999999999}, "otra-clave-que-no-es-la-nuestra-123456", ALGORITMO_JWT)

    assert leer_token(falso) is None


def test_token_sin_firma_no_vale() -> None:
    """Ataque clásico: un token con algoritmo "none" (sin firma) debe rechazarse."""
    sin_firma = jwt.encode({"sub": "42", "exp": 9999999999}, key=None, algorithm="none")

    assert leer_token(sin_firma) is None


def test_la_clave_secreta_es_suficientemente_larga() -> None:
    assert len(get_settings().jwt_secreto) >= 32
