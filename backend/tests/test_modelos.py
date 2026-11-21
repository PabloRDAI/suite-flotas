"""Tests de los modelos: comprueban que la BASE DE DATOS hace cumplir las reglas.

Usan la fixture `db` (conftest.py): todo lo que se inserta se deshace al final.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import EstadoVehiculo
from tests.fabricas import crear_centro, crear_empresa, crear_tipo, crear_usuario, nuevo_vehiculo

# --- GEN-01: multiempresa ----------------------------------------------------


def test_todas_las_tablas_de_negocio_tienen_empresa_id() -> None:
    """GEN-01: salvo la propia empresa, toda tabla va ligada a una empresa.

    Este test protege el futuro: si más adelante alguien crea una tabla sin
    empresa_id, fallará aquí.
    """
    for nombre, tabla in Base.metadata.tables.items():
        if nombre == "empresa":
            continue
        assert "empresa_id" in tabla.columns, f"La tabla '{nombre}' no tiene empresa_id"
        assert not tabla.columns["empresa_id"].nullable, f"'{nombre}.empresa_id' admite nulos"


def test_vehiculo_no_puede_usar_un_centro_de_otra_empresa(db: Session) -> None:
    empresa_a = crear_empresa(db, "Empresa A")
    empresa_b = crear_empresa(db, "Empresa B")
    tipo_a = crear_tipo(db, empresa_a)
    centro_de_b = crear_centro(db, empresa_b)

    db.add(nuevo_vehiculo(empresa_a, centro_de_b, tipo_a))

    with pytest.raises(IntegrityError, match="fk_vehiculo_centro_misma_empresa"):
        db.flush()


def test_vehiculo_no_puede_usar_un_tipo_de_otra_empresa(db: Session) -> None:
    empresa_a = crear_empresa(db, "Empresa A")
    empresa_b = crear_empresa(db, "Empresa B")
    centro_a = crear_centro(db, empresa_a)
    tipo_de_b = crear_tipo(db, empresa_b)

    db.add(nuevo_vehiculo(empresa_a, centro_a, tipo_de_b))

    with pytest.raises(IntegrityError, match="fk_vehiculo_tipo_misma_empresa"):
        db.flush()


# --- FLO-01: ficha de vehículo -----------------------------------------------


def test_crear_vehiculo_con_valores_por_defecto(db: Session) -> None:
    empresa = crear_empresa(db)
    vehiculo = nuevo_vehiculo(empresa, crear_centro(db, empresa), crear_tipo(db, empresa))
    db.add(vehiculo)
    db.flush()
    db.refresh(vehiculo)  # relee la fila para ver lo que puso la BD (fechas)

    assert vehiculo.id is not None
    assert vehiculo.estado == EstadoVehiculo.OPERATIVO
    assert vehiculo.km_actuales == 0
    assert vehiculo.activo is True
    assert vehiculo.creado_en is not None


def test_matricula_repetida_en_la_misma_empresa_se_rechaza(db: Session) -> None:
    empresa = crear_empresa(db)
    centro, tipo = crear_centro(db, empresa), crear_tipo(db, empresa)
    db.add(nuevo_vehiculo(empresa, centro, tipo, matricula="1234ABC"))
    db.flush()

    db.add(nuevo_vehiculo(empresa, centro, tipo, matricula="1234ABC"))

    with pytest.raises(IntegrityError, match="uq_vehiculo_empresa_id_matricula"):
        db.flush()


def test_la_misma_matricula_en_otra_empresa_se_permite(db: Session) -> None:
    for nombre in ("Empresa A", "Empresa B"):
        empresa = crear_empresa(db, nombre)
        db.add(nuevo_vehiculo(empresa, crear_centro(db, empresa), crear_tipo(db, empresa), matricula="1234ABC"))

    db.flush()  # no lanza error


def test_km_negativos_se_rechazan(db: Session) -> None:
    empresa = crear_empresa(db)
    db.add(nuevo_vehiculo(empresa, crear_centro(db, empresa), crear_tipo(db, empresa), km_actuales=-1))

    with pytest.raises(IntegrityError, match="ck_vehiculo_km_no_negativos"):
        db.flush()


def test_la_bd_rechaza_un_estado_que_no_existe(db: Session) -> None:
    """Aunque alguien salte el código Python y escriba SQL a mano, el CHECK lo impide."""
    empresa = crear_empresa(db)
    vehiculo = nuevo_vehiculo(empresa, crear_centro(db, empresa), crear_tipo(db, empresa))
    db.add(vehiculo)
    db.flush()

    with pytest.raises(IntegrityError, match="ck_vehiculo_estado_vehiculo"):
        db.execute(text("UPDATE vehiculo SET estado = 'volando' WHERE id = :id"), {"id": vehiculo.id})


# --- GEN-03 y FLO-02: centros y tipos por empresa ----------------------------


def test_nombre_de_centro_unico_dentro_de_la_empresa(db: Session) -> None:
    empresa = crear_empresa(db)
    crear_centro(db, empresa, "Cochera Norte")

    with pytest.raises(IntegrityError, match="uq_centro_empresa_id_nombre"):
        crear_centro(db, empresa, "Cochera Norte")


def test_cada_empresa_define_sus_propios_tipos(db: Session) -> None:
    """FLO-02: dos empresas pueden tener un tipo con el mismo nombre, cada una el suyo."""
    tipo_a = crear_tipo(db, crear_empresa(db, "Empresa A"), "Cisterna")
    tipo_b = crear_tipo(db, crear_empresa(db, "Empresa B"), "Cisterna")

    assert tipo_a.id != tipo_b.id


# --- Usuarios ----------------------------------------------------------------


def test_email_de_usuario_unico(db: Session) -> None:
    crear_usuario(db, crear_empresa(db, "Empresa A"), "ana@example.com")

    with pytest.raises(IntegrityError, match="uq_usuario_email"):
        crear_usuario(db, crear_empresa(db, "Empresa B"), "ana@example.com")
