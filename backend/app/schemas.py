"""Esquemas Pydantic: lo que ENTRA y SALE por la API (distinto de los modelos de BD).

- Validan la entrada (formato de email, longitudes…) antes de tocar la BD.
- Deciden qué se devuelve: p. ej. UsuarioSalida no tiene hash_password.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Combustible, EstadoVehiculo, RolUsuario

# --- Autenticación -----------------------------------------------------------


class LoginEntrada(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioSalida(BaseModel):
    # from_attributes: permite construirlo directamente desde un objeto Usuario de SQLAlchemy.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    rol: RolUsuario
    empresa_id: int


# --- Vehículos ---------------------------------------------------------------


class VehiculoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    matricula: str
    marca: str
    modelo: str
    anio: int
    capacidad: int | None
    combustible: Combustible
    km_actuales: int
    estado: EstadoVehiculo
    centro_id: int
    tipo_id: int
    activo: bool
