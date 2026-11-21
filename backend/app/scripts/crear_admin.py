"""Crea una empresa y su usuario administrador.

Uso (con el entorno virtual activado, desde backend/):

    python -m app.scripts.crear_admin --empresa "Transportes Ficticios" --email admin@example.com --nombre "Ana Admin"

La contraseña se pide por teclado sin mostrarse (no queda en el historial de la terminal).
"""

import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Empresa, RolUsuario, Usuario
from app.seguridad import hash_password

LONGITUD_MINIMA = 10


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea una empresa y su usuario administrador.")
    parser.add_argument("--empresa", required=True, help="Nombre de la empresa")
    parser.add_argument("--email", required=True, help="Email del administrador (para el login)")
    parser.add_argument("--nombre", required=True, help="Nombre del administrador")
    args = parser.parse_args()

    email = args.email.strip().lower()
    try:
        # Misma validación que el login: si el formato no es válido, nunca podría entrar.
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        print(f"Error: '{email}' no es un email válido (usa p. ej. un dominio example.com).", file=sys.stderr)
        return 1

    password = getpass.getpass(f"Contraseña para {email} (mín. {LONGITUD_MINIMA} caracteres): ")
    if len(password) < LONGITUD_MINIMA:
        print(f"Error: la contraseña debe tener al menos {LONGITUD_MINIMA} caracteres.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repite la contraseña: "):
        print("Error: las contraseñas no coinciden.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(func.lower(Usuario.email) == email)):
            print(f"Error: ya existe un usuario con el email {email}.", file=sys.stderr)
            return 1

        empresa = Empresa(nombre=args.empresa.strip())
        db.add(empresa)
        db.flush()
        db.add(
            Usuario(
                empresa_id=empresa.id,
                email=email,
                nombre=args.nombre.strip(),
                hash_password=hash_password(password),
                rol=RolUsuario.ADMIN,
            )
        )
        db.commit()
        print(f"Creada la empresa '{empresa.nombre}' (id {empresa.id}) con el administrador {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
