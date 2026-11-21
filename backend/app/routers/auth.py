"""Autenticación: login y datos del usuario conectado (GEN-02)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import Db, UsuarioActual
from app.models import Usuario
from app.schemas import LoginEntrada, TokenSalida, UsuarioSalida
from app.seguridad import crear_token, verificar_password_o_simular

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/login")
def login(datos: LoginEntrada, db: Db) -> TokenSalida:
    """Comprueba email y contraseña y devuelve un token de sesión.

    El mensaje de error es el mismo si el email no existe, si la contraseña es
    incorrecta o si el usuario está desactivado: así no se revela qué emails existen.
    """
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == datos.email.lower()))

    password_ok = verificar_password_o_simular(datos.password, usuario.hash_password if usuario else None)
    if usuario is None or not password_ok or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenSalida(access_token=crear_token(usuario.id))


@router.get("/yo")
def yo(usuario: UsuarioActual) -> UsuarioSalida:
    """Datos del usuario dueño del token (útil para el frontend tras el login)."""
    return UsuarioSalida.model_validate(usuario)
