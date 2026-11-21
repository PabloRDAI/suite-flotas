"""Modelos de la base de datos.

Importarlos aquí hace que se registren en Base.metadata: así Alembic (env.py)
y los tests los ven todos con un solo "import app.models".
"""

from app.models.asignacion import Asignacion
from app.models.centro import Centro, TipoCentro
from app.models.empresa import Empresa
from app.models.lectura_km import LecturaKm
from app.models.mantenimiento import EstadoPlan, PlanMantenimiento, TareaPlan
from app.models.persona import Persona, Puesto
from app.models.usuario import RolUsuario, Usuario
from app.models.vencimiento import AplicaA, TipoVencimiento, Vencimiento
from app.models.vehiculo import Combustible, EstadoVehiculo, TipoVehiculo, UnidadCapacidad, Vehiculo

__all__ = [
    "AplicaA",
    "Asignacion",
    "Centro",
    "Combustible",
    "Empresa",
    "EstadoPlan",
    "EstadoVehiculo",
    "LecturaKm",
    "Persona",
    "PlanMantenimiento",
    "Puesto",
    "RolUsuario",
    "TareaPlan",
    "TipoCentro",
    "TipoVehiculo",
    "TipoVencimiento",
    "UnidadCapacidad",
    "Usuario",
    "Vehiculo",
    "Vencimiento",
]
