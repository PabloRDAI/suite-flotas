"""Crea la empresa de demostración con datos ficticios (GEN-04).

Uso (con el entorno virtual activado, desde backend/):

    python -m app.scripts.demo              # la crea (error si ya existe)
    python -m app.scripts.demo --reiniciar  # la borra y la vuelve a crear

Solo toca la empresa demo (usuarios @demo.example.com); nunca otras empresas.
"""

import argparse
import sys

from app.db import SessionLocal
from app.servicios.demo import NOMBRE_EMPRESA, PASSWORD_DEMO, DemoYaExiste, crear_empresa_demo


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea la empresa de demostración con datos ficticios.")
    parser.add_argument("--reiniciar", action="store_true", help="Borra la empresa demo y la vuelve a crear")
    parser.add_argument(
        "--password", default=PASSWORD_DEMO, help=f"Contraseña de los usuarios demo (por defecto: {PASSWORD_DEMO})"
    )
    args = parser.parse_args()
    if len(args.password) < 10:
        print("Error: la contraseña debe tener al menos 10 caracteres.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        try:
            r = crear_empresa_demo(db, password=args.password, reiniciar=args.reiniciar)
        except DemoYaExiste as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        db.commit()

    print(f"Creada '{NOMBRE_EMPRESA}' (id {r.empresa_id}):")
    print(f"  {r.centros} centros, {r.vehiculos} vehículos, {r.lecturas_km} lecturas de km, {r.vencimientos} vencimientos")
    print(f"  No aptos para salir: {', '.join(r.no_aptos) or 'ninguno'}")
    print(f"  Con documentos en ámbar: {', '.join(r.en_ambar) or 'ninguno'}")
    print(f"  {r.personas} personas; con documentación caducada: {', '.join(r.personas_en_rojo) or 'ninguna'}")
    print(f"  Personas con documentación a punto de caducar: {', '.join(r.personas_en_ambar) or 'ninguna'}")
    print(f"  {r.asignaciones} asignaciones; con aviso de documentación: {', '.join(r.asignaciones_con_aviso) or 'ninguna'}")
    print(f"  {r.planes} planes preventivos. Vencidos: {'; '.join(r.preventivos_vencidos) or 'ninguno'}")
    print(f"  Preventivos próximos: {'; '.join(r.preventivos_proximos) or 'ninguno'}")
    print(f"Usuarios (contraseña: {args.password}):")
    for email in r.usuarios:
        print(f"  {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
