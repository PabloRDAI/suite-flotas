"""Dependencias de FastAPI para autenticación y permisos.

Se usan en los endpoints así:

    def mi_endpoint(usuario: UsuarioActual): ...                      # cualquiera con sesión
    def borrar(usuario: Annotated[Usuario, Depends(requiere_roles(RolUsuario.ADMIN))]): ...

FastAPI las ejecuta ANTES del endpoint: si fallan, el endpoint ni se ejecuta.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RolUsuario, Usuario
from app.seguridad import leer_token

# Lee la cabecera "Authorization: Bearer <token>". auto_error=False para
# devolver nosotros un 401 con un mensaje claro (y no el 403 por defecto).
_bearer = HTTPBearer(auto_error=False, description="Token obtenido en POST /auth/login")

Db = Annotated[Session, Depends(get_db)]


def _no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},  # indica al cliente cómo autenticarse
    )


def get_usuario_actual(
    db: Db,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    """Identifica al usuario a partir del token. 401 si no hay token válido."""
    if credenciales is None:
        raise _no_autenticado("Falta el token de sesión")

    usuario_id = leer_token(credenciales.credentials)
    if usuario_id is None:
        raise _no_autenticado("Token no válido o caducado")

    # Se lee el usuario de la BD en cada petición: si lo desactivan o le cambian
    # el rol, surte efecto al momento (no hay que esperar a que caduque el token).
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise _no_autenticado("Usuario no válido o desactivado")
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_usuario_actual)]


def requiere_roles(*roles: RolUsuario) -> Callable[[Usuario], Usuario]:
    """Fábrica de dependencias: deja pasar solo a los usuarios con alguno de estos roles.

    Primero exige sesión (401 si no hay) y después el rol (403 si no lo tiene).
    """

    def comprobar_rol(usuario: UsuarioActual) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no tiene permiso para esta acción",
            )
        return usuario

    return comprobar_rol


# Permisos con nombre, para que cada endpoint se lea fácil:
# - SoloAdmin: configuración de la empresa (centros, tipos de vehículo…).
# - GestionFlota: alta, edición y baja de vehículos (gerente y jefe de tráfico).
SoloAdmin = Annotated[Usuario, Depends(requiere_roles(RolUsuario.ADMIN))]
GestionFlota = Annotated[Usuario, Depends(requiere_roles(RolUsuario.ADMIN, RolUsuario.TRAFICO))]
# - GestionPersonal: alta, edición, baja y documentación del personal (gerente y jefe de tráfico).
GestionPersonal = GestionFlota
