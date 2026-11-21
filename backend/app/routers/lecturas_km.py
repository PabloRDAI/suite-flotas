"""Lecturas de km de un vehículo (FLO-05).

"No se acepta una lectura menor que la anterior; los km actuales del vehículo
son los de la última lectura."

La regla está en app/reglas/km.py (Python puro, con sus propios tests); este
router solo carga los datos, llama a la regla y guarda el resultado.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, GestionFlota, UsuarioActual
from app.models import LecturaKm, Vehiculo
from app.reglas.km import Lectura, LecturaNoValida, comprobar_lectura, km_actuales
from app.routers.vehiculos import vehiculo_de_mi_empresa
from app.schemas import LecturaKmCrear, LecturaKmSalida

router = APIRouter(prefix="/vehiculos/{vehiculo_id}/km", tags=["vehículos"])


def _lecturas(db: Db, vehiculo: Vehiculo) -> list[LecturaKm]:
    """Lecturas del vehículo, de la más reciente a la más antigua."""
    return list(
        db.scalars(
            select(LecturaKm)
            .where(LecturaKm.vehiculo_id == vehiculo.id, LecturaKm.empresa_id == vehiculo.empresa_id)
            .order_by(LecturaKm.fecha.desc(), LecturaKm.km.desc(), LecturaKm.id.desc())
        )
    )


def _como_reglas(lecturas: list[LecturaKm]) -> list[Lectura]:
    """Convierte las filas de la BD al formato del motor de reglas."""
    return [Lectura(fecha=l.fecha, km=l.km) for l in lecturas]


@router.get("")
def historial_km(vehiculo_id: int, usuario: UsuarioActual, db: Db) -> list[LecturaKmSalida]:
    """Historial de lecturas de km (también de vehículos dados de baja)."""
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=False)
    return [LecturaKmSalida.model_validate(l) for l in _lecturas(db, vehiculo)]


@router.post("", status_code=status.HTTP_201_CREATED)
def registrar_lectura(vehiculo_id: int, datos: LecturaKmCrear, usuario: UsuarioActual, db: Db) -> LecturaKmSalida:
    """Registra una lectura (cualquier rol: el conductor es quien ve el cuentakilómetros).

    - 422 si los km retroceden respecto a la lectura anterior (o superan a una
      posterior, si la lectura es de una fecha pasada) o si la fecha es futura.
    - 404 si el vehículo no existe, es de otra empresa o está dado de baja.
    """
    # Bloqueo: si dos personas registran km a la vez, la segunda espera a que
    # termine la primera y valida contra datos ya actualizados.
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True, bloquear=True)
    existentes = _lecturas(db, vehiculo)
    nueva = Lectura(fecha=datos.fecha or date.today(), km=datos.km)

    try:
        comprobar_lectura(nueva, _como_reglas(existentes), hoy=date.today())
    except LecturaNoValida as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    lectura = LecturaKm(
        empresa_id=usuario.empresa_id,
        vehiculo_id=vehiculo.id,
        fecha=nueva.fecha,
        km=nueva.km,
        registrada_por_id=usuario.id,
    )
    db.add(lectura)
    # FLO-05: los km actuales son los de la última lectura (una atrasada no los cambia).
    vehiculo.km_actuales = km_actuales([*_como_reglas(existentes), nueva])
    db.commit()
    return LecturaKmSalida.model_validate(lectura)


@router.delete("/{lectura_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_lectura(vehiculo_id: int, lectura_id: int, usuario: GestionFlota, db: Db) -> Response:
    """Borra una lectura errónea (admin y tráfico) y recalcula los km actuales.

    Sin esta opción, un error de tecleo (1.000.000 en vez de 100.000) bloquearía
    todas las lecturas futuras. No se puede borrar la única lectura del vehículo.
    """
    vehiculo = vehiculo_de_mi_empresa(db, usuario, vehiculo_id, solo_activos=True, bloquear=True)
    existentes = _lecturas(db, vehiculo)
    lectura = next((l for l in existentes if l.id == lectura_id), None)
    if lectura is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lectura no encontrada")
    if len(existentes) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede borrar la única lectura del vehículo")

    db.delete(lectura)
    vehiculo.km_actuales = km_actuales(_como_reglas([l for l in existentes if l.id != lectura_id]))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
