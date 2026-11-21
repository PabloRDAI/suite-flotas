"""Vehículos (FLO-01). De momento: listar y dar de baja, con permisos (GEN-01, GEN-02).

El resto del CRUD (crear, editar, consultar uno) se añadirá a este mismo router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, UsuarioActual, requiere_roles
from app.models import EstadoVehiculo, RolUsuario, Usuario, Vehiculo
from app.schemas import VehiculoSalida

router = APIRouter(prefix="/vehiculos", tags=["vehículos"])

# Quién puede dar de baja vehículos: gerente y jefe de tráfico.
PuedeGestionarFlota = Annotated[Usuario, Depends(requiere_roles(RolUsuario.ADMIN, RolUsuario.TRAFICO))]


@router.get("")
def listar_vehiculos(usuario: UsuarioActual, db: Db) -> list[VehiculoSalida]:
    """Vehículos activos de la empresa del usuario (cualquier rol con sesión)."""
    vehiculos = db.scalars(
        select(Vehiculo)
        # GEN-01: SIEMPRE filtrar por la empresa del usuario conectado.
        .where(Vehiculo.empresa_id == usuario.empresa_id, Vehiculo.activo)
        .order_by(Vehiculo.matricula)
    )
    return [VehiculoSalida.model_validate(v) for v in vehiculos]


@router.delete("/{vehiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_vehiculo(vehiculo_id: int, usuario: PuedeGestionarFlota, db: Db) -> Response:
    """Baja lógica (FLO-01): el vehículo no se borra, se marca como inactivo y "de baja".

    - 403 si el rol no puede gestionar la flota (p. ej. un conductor).
    - 404 si el vehículo no existe O es de otra empresa: no revelamos que existe.
    """
    vehiculo = db.scalar(
        select(Vehiculo).where(Vehiculo.id == vehiculo_id, Vehiculo.empresa_id == usuario.empresa_id)
    )
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")

    vehiculo.activo = False
    vehiculo.estado = EstadoVehiculo.BAJA
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
