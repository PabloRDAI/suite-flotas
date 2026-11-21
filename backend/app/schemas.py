"""Esquemas Pydantic: lo que ENTRA y SALE por la API (distinto de los modelos de BD).

- Validan la entrada (formato de email, longitudes…) antes de tocar la BD.
- Deciden qué se devuelve: p. ej. UsuarioSalida no tiene hash_password.
- Los de entrada usan extra="forbid": un campo no previsto (p. ej. empresa_id o
  estado) se rechaza con 422 en vez de ignorarse en silencio.
"""

import re
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models import Combustible, EstadoVehiculo, RolUsuario, TipoCentro, UnidadCapacidad

# --- Tipos reutilizables -----------------------------------------------------

# Texto obligatorio: se quitan los espacios de los extremos y no puede quedar vacío.
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def normalizar_matricula(valor: str) -> str:
    """'1234 abc', '1234-ABC' y '1234ABC' son la misma matrícula: se guarda '1234ABC'.

    Así la regla "matrícula única en la empresa" no se puede saltar escribiéndola
    con espacios, guiones o minúsculas.
    """
    limpia = re.sub(r"[\s\-]", "", valor).upper()
    if not re.fullmatch(r"[A-Z0-9]{2,15}", limpia):
        raise ValueError("La matrícula solo puede tener letras y números (entre 2 y 15)")
    return limpia


def validar_anio(valor: int) -> int:
    maximo = date.today().year + 1  # se admite el modelo del año que viene
    if not 1950 <= valor <= maximo:
        raise ValueError(f"El año debe estar entre 1950 y {maximo}")
    return valor


Matricula = Annotated[str, AfterValidator(normalizar_matricula)]
Anio = Annotated[int, AfterValidator(validar_anio)]
Capacidad = Annotated[int, Field(gt=0, le=100_000)]


class EntradaEstricta(BaseModel):
    """Base de los esquemas de entrada: rechaza campos desconocidos."""

    model_config = ConfigDict(extra="forbid")


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


# --- Centros (GEN-03) --------------------------------------------------------


class CentroCrear(EntradaEstricta):
    nombre: Annotated[Texto, Field(max_length=100)]
    tipo: TipoCentro = TipoCentro.COCHERA
    direccion: Annotated[Texto, Field(max_length=200)] | None = None


class CentroSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoCentro
    direccion: str | None
    activo: bool


# --- Tipos de vehículo (FLO-02) ----------------------------------------------


class TipoVehiculoCrear(EntradaEstricta):
    nombre: Annotated[Texto, Field(max_length=60)]
    unidad_capacidad: UnidadCapacidad = UnidadCapacidad.PLAZAS


class TipoVehiculoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    unidad_capacidad: UnidadCapacidad
    activo: bool


# --- Vehículos (FLO-01) ------------------------------------------------------


class VehiculoCrear(EntradaEstricta):
    """Alta de vehículo. No incluye empresa_id (sale del usuario) ni estado (lo calcula el sistema)."""

    matricula: Matricula
    centro_id: int
    tipo_id: int
    marca: Annotated[Texto, Field(max_length=50)]
    modelo: Annotated[Texto, Field(max_length=80)]
    anio: Anio
    capacidad: Capacidad | None = None
    combustible: Combustible
    # Km en el momento del alta. Después solo cambian con lecturas de km (FLO-05).
    km_actuales: Annotated[int, Field(ge=0)] = 0


class VehiculoEditar(EntradaEstricta):
    """Edición parcial (PATCH): solo se cambian los campos que se envían.

    No se pueden editar aquí: km_actuales (FLO-05, lecturas de km), estado
    (FLO-03, lo calcula el motor de reglas) ni activo (baja con DELETE).
    """

    matricula: Matricula | None = None
    centro_id: int | None = None
    tipo_id: int | None = None
    marca: Annotated[Texto, Field(max_length=50)] | None = None
    modelo: Annotated[Texto, Field(max_length=80)] | None = None
    anio: Anio | None = None
    capacidad: Capacidad | None = None
    combustible: Combustible | None = None

    @model_validator(mode="after")
    def no_vaciar_campos_obligatorios(self) -> "VehiculoEditar":
        """Enviar un campo con null significa "vaciarlo": solo se permite en capacidad."""
        anulables = {"capacidad"}
        vaciados = [c for c in self.model_fields_set if getattr(self, c) is None and c not in anulables]
        if vaciados:
            raise ValueError(f"Estos campos no pueden quedar vacíos: {', '.join(sorted(vaciados))}")
        return self


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
