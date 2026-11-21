"""Funciones para crear datos de prueba con valores por defecto razonables.

Cada test solo indica lo que le importa; el resto lo rellenan estas "fábricas".
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Centro,
    Combustible,
    Empresa,
    RolUsuario,
    TipoVehiculo,
    UnidadCapacidad,
    Usuario,
    Vehiculo,
)
from app.seguridad import crear_token, hash_password


def crear_empresa(db: Session, nombre: str = "Transportes Ficticios S.L.") -> Empresa:
    empresa = Empresa(nombre=nombre)
    db.add(empresa)
    db.flush()  # envía el INSERT a la BD (dentro de la transacción) y obtiene el id
    return empresa


def crear_centro(db: Session, empresa: Empresa, nombre: str = "Cochera central") -> Centro:
    centro = Centro(empresa_id=empresa.id, nombre=nombre)
    db.add(centro)
    db.flush()
    return centro


def crear_tipo(db: Session, empresa: Empresa, nombre: str = "Autobús") -> TipoVehiculo:
    tipo = TipoVehiculo(empresa_id=empresa.id, nombre=nombre, unidad_capacidad=UnidadCapacidad.PLAZAS)
    db.add(tipo)
    db.flush()
    return tipo


def crear_usuario(
    db: Session,
    empresa: Empresa,
    email: str = "gerente@example.com",
    rol: RolUsuario = RolUsuario.ADMIN,
    password: str | None = None,
    activo: bool = True,
) -> Usuario:
    """Crea un usuario. Con `password` se guarda su hash real (para tests de login)."""
    usuario = Usuario(
        empresa_id=empresa.id,
        email=email,
        nombre="Usuario de prueba",
        hash_password=hash_password(password) if password else "no-es-un-hash-real",
        rol=rol,
        activo=activo,
    )
    db.add(usuario)
    db.flush()
    return usuario


def cabeceras(usuario: Usuario) -> dict[str, str]:
    """Cabecera HTTP con un token válido para `usuario` (sin pasar por el login)."""
    return {"Authorization": f"Bearer {crear_token(usuario.id)}"}


def crear_vehiculo(db: Session, empresa: Empresa, matricula: str = "1234ABC") -> Vehiculo:
    """Crea un vehículo con su centro y su tipo (todo de la misma empresa)."""
    vehiculo = nuevo_vehiculo(
        empresa,
        crear_centro(db, empresa, f"Centro {matricula}"),
        crear_tipo(db, empresa, f"Tipo {matricula}"),
        matricula=matricula,
    )
    db.add(vehiculo)
    db.flush()
    return vehiculo


def nuevo_vehiculo(empresa: Empresa, centro: Centro, tipo: TipoVehiculo, **cambios: Any) -> Vehiculo:
    """Crea el objeto Vehiculo SIN guardarlo (el test decide cuándo hacer flush)."""
    datos: dict[str, Any] = {
        "empresa_id": empresa.id,
        "centro_id": centro.id,
        "tipo_id": tipo.id,
        "matricula": "1234ABC",
        "marca": "Marca Ficticia",
        "modelo": "Modelo X",
        "anio": 2020,
        "capacidad": 55,
        "combustible": Combustible.DIESEL,
    }
    datos.update(cambios)
    return Vehiculo(**datos)
