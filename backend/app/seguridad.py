"""Contraseñas (hash Argon2) y tokens de sesión (JWT)."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

# PasswordHasher usa los parámetros recomendados de Argon2id (memoria, tiempo
# y paralelismo). Cada hash lleva su propia "sal" aleatoria: dos usuarios con
# la misma contraseña tienen hashes distintos.
_hasher = PasswordHasher()

# Hash de una contraseña cualquiera, para gastar el mismo tiempo cuando el
# email no existe (ver verificar_password_o_simular).
_HASH_FICTICIO = _hasher.hash("contraseña-ficticia-para-igualar-tiempos")

ALGORITMO_JWT = "HS256"


# --- Contraseñas -------------------------------------------------------------


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2 de la contraseña (empieza por '$argon2id$')."""
    return _hasher.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    """True si la contraseña corresponde al hash guardado."""
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerificationError, InvalidHashError):
        return False


def verificar_password_o_simular(password: str, hash_guardado: str | None) -> bool:
    """Como verificar_password, pero si no hay usuario (hash None) tarda lo mismo.

    Así un atacante no puede averiguar qué emails existen midiendo cuánto
    tarda el login (si el email no existe y respondiéramos al instante, se notaría).
    """
    if hash_guardado is None:
        verificar_password(password, _HASH_FICTICIO)
        return False
    return verificar_password(password, hash_guardado)


# --- Tokens ------------------------------------------------------------------


def crear_token(usuario_id: int, minutos: int | None = None) -> str:
    """Crea un token firmado que identifica al usuario y caduca en `minutos`."""
    ajustes = get_settings()
    ahora = datetime.now(UTC)
    contenido = {
        "sub": str(usuario_id),  # "subject": a quién pertenece el token
        "iat": ahora,  # "issued at": cuándo se emitió
        "exp": ahora + timedelta(minutes=minutos if minutos is not None else ajustes.jwt_minutos),
    }
    return jwt.encode(contenido, ajustes.jwt_secreto, algorithm=ALGORITMO_JWT)


def leer_token(token: str) -> int | None:
    """Devuelve el id de usuario del token, o None si es falso, está alterado o ha caducado."""
    try:
        contenido = jwt.decode(
            token,
            get_settings().jwt_secreto,
            algorithms=[ALGORITMO_JWT],  # solo aceptamos nuestro algoritmo
            options={"require": ["sub", "exp"]},
        )
        return int(contenido["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
