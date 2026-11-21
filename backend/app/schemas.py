"""Esquemas Pydantic: lo que ENTRA y SALE por la API (distinto de los modelos de BD).

- Validan la entrada (formato de email, longitudes…) antes de tocar la BD.
- Deciden qué se devuelve: p. ej. UsuarioSalida no tiene hash_password.
- Los de entrada usan extra="forbid": un campo no previsto (p. ej. empresa_id o
  estado) se rechaza con 422 en vez de ignorarse en silencio.
"""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models import AplicaA, Combustible, EstadoVehiculo, Puesto, RolUsuario, TipoCentro, UnidadCapacidad
from app.reglas.vencimientos import Semaforo

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


class TipoVencimientoCrear(EntradaEstricta):
    """Tipo de documento que caduca (FLO-06). Los plazos los decide la empresa, no el código."""

    nombre: Annotated[Texto, Field(max_length=80)]
    aplica_a: AplicaA = AplicaA.VEHICULO
    dias_aviso: Annotated[int, Field(ge=0, le=365)] = 30
    bloquea_salida: bool = True


class TipoVencimientoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    aplica_a: AplicaA
    dias_aviso: int
    bloquea_salida: bool
    activo: bool


class VencimientoCrear(EntradaEstricta):
    tipo_id: int
    fecha_caducidad: date
    notas: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class VencimientoSalida(BaseModel):
    """Un documento con su semáforo ya calculado por el motor de reglas."""

    id: int
    tipo_id: int
    tipo_nombre: str
    fecha_caducidad: date
    notas: str | None
    dias_restantes: int  # negativo si ya caducó
    semaforo: Semaforo
    vigente: bool  # False si es historial (hay otro del mismo tipo que caduca más tarde)


class AptitudSalida(BaseModel):
    """FLO-07: ¿puede salir el vehículo?"""

    apto: bool
    motivos: list[str]
    semaforo: Semaforo  # el peor de su documentación vigente


# --- Personal (PER-01) -------------------------------------------------------
# Privacidad (RGPD): solo estos campos. No hay DNI ni datos bancarios, y como las
# entradas son estrictas (extra="forbid"), enviarlos se rechaza con 422.


class PersonaCrear(EntradaEstricta):
    nombre: Annotated[Texto, Field(max_length=150)]
    puesto: Puesto
    centro_id: int
    fecha_alta: date
    usuario_id: int | None = None


class PersonaEditar(EntradaEstricta):
    """Edición parcial. La baja va por DELETE; usuario_id=null desenlaza el usuario."""

    nombre: Annotated[Texto, Field(max_length=150)] | None = None
    puesto: Puesto | None = None
    centro_id: int | None = None
    fecha_alta: date | None = None
    usuario_id: int | None = None

    @model_validator(mode="after")
    def no_vaciar_campos_obligatorios(self) -> "PersonaEditar":
        vaciados = [c for c in self.model_fields_set if getattr(self, c) is None and c != "usuario_id"]
        if vaciados:
            raise ValueError(f"Estos campos no pueden quedar vacíos: {', '.join(sorted(vaciados))}")
        return self


class PersonaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    puesto: Puesto
    centro_id: int
    fecha_alta: date
    activo: bool
    fecha_baja: date | None
    usuario_id: int | None
    # PER-02: peor semáforo de su documentación vigente (mismas reglas que FLO-06).
    semaforo: Semaforo = Semaforo.VERDE


# --- Asignaciones conductor-vehículo (PER-03, PER-04) ------------------------


class AsignacionCrear(EntradaEstricta):
    persona_id: int
    vehiculo_id: int
    desde: date | None = None  # sin fecha: hoy
    hasta: date | None = None  # sin fecha: hasta nuevo aviso
    habitual: bool = True
    notas: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @model_validator(mode="after")
    def fechas_en_orden(self) -> "AsignacionCrear":
        if self.desde and self.hasta and self.hasta < self.desde:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        return self


class AsignacionFinalizar(EntradaEstricta):
    hasta: date | None = None  # sin fecha: ayer (para que la nueva pueda empezar hoy)


class AsignacionSalida(BaseModel):
    id: int
    persona_id: int
    persona_nombre: str
    vehiculo_id: int
    matricula: str
    desde: date
    hasta: date | None
    habitual: bool
    notas: str | None
    vigente: bool  # ¿está en vigor hoy?
    # PER-04: avisos por documentación caducada del conductor (no bloquean).
    avisos: list[str]


class VehiculoPanel(BaseModel):
    """Un vehículo en el panel, con su aptitud ya calculada."""

    id: int
    matricula: str
    marca: str
    modelo: str
    tipo_id: int
    centro_id: int
    km_actuales: int
    estado: EstadoVehiculo
    apto: bool
    motivos: list[str]
    semaforo: Semaforo  # peor semáforo de su documentación vigente


class AlertaPanel(BaseModel):
    """Algo que requiere atención. Hoy: vencimientos; más adelante, preventivos y averías."""

    tipo: Literal["vencimiento"]
    semaforo: Semaforo
    vehiculo_id: int
    matricula: str
    mensaje: str
    fecha: date
    dias_restantes: int


class ContadoresPanel(BaseModel):
    total: int
    operativo: int
    en_taller: int
    inmovilizado: int
    aptos: int
    no_aptos: int


class PanelSalida(BaseModel):
    """FLO-04: contadores, tabla y alertas, calculados sobre la MISMA lista de vehículos."""

    fecha: date
    contadores: ContadoresPanel
    vehiculos: list[VehiculoPanel]
    alertas: list[AlertaPanel]


class LecturaKmCrear(EntradaEstricta):
    """Nueva lectura de km (FLO-05). Sin fecha, se usa la de hoy."""

    km: Annotated[int, Field(ge=0, le=10_000_000)]
    fecha: date | None = None


class LecturaKmSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehiculo_id: int
    fecha: date
    km: int
    registrada_por_id: int | None


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
