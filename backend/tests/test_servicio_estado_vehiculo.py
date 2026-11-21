"""Tests del servicio que aplica la regla 1 a un vehículo de la base de datos."""

from sqlalchemy.orm import Session

from app.models import EstadoVehiculo
from app.servicios.estado_vehiculo import actualizar_estado
from tests.fabricas import crear_empresa, crear_vehiculo


def test_un_vehiculo_activo_sin_pendientes_queda_operativo(db: Session) -> None:
    vehiculo = crear_vehiculo(db, crear_empresa(db))

    assert actualizar_estado(db, vehiculo) == EstadoVehiculo.OPERATIVO
    assert vehiculo.estado == EstadoVehiculo.OPERATIVO


def test_un_vehiculo_inactivo_queda_de_baja(db: Session) -> None:
    vehiculo = crear_vehiculo(db, crear_empresa(db))
    vehiculo.activo = False

    actualizar_estado(db, vehiculo)

    assert vehiculo.estado == EstadoVehiculo.BAJA


def test_el_estado_guardado_se_corrige_si_no_coincide_con_la_regla(db: Session) -> None:
    """El estado nunca se fija a mano: si alguien lo dejó mal, el motor lo corrige."""
    vehiculo = crear_vehiculo(db, crear_empresa(db))
    vehiculo.estado = EstadoVehiculo.EN_TALLER  # sin ninguna OT que lo justifique

    actualizar_estado(db, vehiculo)

    assert vehiculo.estado == EstadoVehiculo.OPERATIVO


def test_el_servicio_no_confirma_la_transaccion(db: Session) -> None:
    """Quien llama decide cuándo hacer commit (junto con el resto de su operación)."""
    vehiculo = crear_vehiculo(db, crear_empresa(db))
    vehiculo.activo = False

    actualizar_estado(db, vehiculo)

    assert vehiculo in db.dirty  # el cambio está pendiente, no confirmado
