"""Alta de vehículos: la usan el endpoint de alta (FLO-01) y la importación (GEN-05)."""

from datetime import date

from sqlalchemy.orm import Session

from app.models import LecturaKm, Vehiculo
from app.schemas import VehiculoCrear
from app.servicios.preventivos import sincronizar_vehiculo


def alta_vehiculo(db: Session, empresa_id: int, usuario_id: int | None, datos: VehiculoCrear, hoy: date) -> Vehiculo:
    """Crea el vehículo con su lectura de km inicial (FLO-05) y sus planes preventivos (MAN-01).

    No hace commit (así la importación crea todos en una sola transacción). Quien llama ya ha
    comprobado que el centro y el tipo son de la empresa y que la matrícula está libre.
    """
    vehiculo = Vehiculo(empresa_id=empresa_id, **datos.model_dump())
    db.add(vehiculo)
    db.flush()  # INSERT ya, para conocer vehiculo.id
    db.add(LecturaKm(empresa_id=empresa_id, vehiculo_id=vehiculo.id, fecha=hoy, km=vehiculo.km_actuales, registrada_por_id=usuario_id))
    sincronizar_vehiculo(db, vehiculo, hoy)  # MAN-01: los planes de su tipo empiezan a contar
    return vehiculo
