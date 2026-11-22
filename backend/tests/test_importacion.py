"""Importación de vehículos y personas desde Excel o CSV (GEN-05).

Criterio: "Al subir la plantilla de ejemplo se crean los registros; las filas con errores
se listan con su motivo sin importar nada a medias."
"""

from datetime import date, datetime
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EstadoPlan, LecturaKm, Persona, PlanMantenimiento, RolUsuario, TareaPlan, Vehiculo
from app.servicios.importacion import ArchivoNoValido, a_entero, a_fecha, leer_tabla, normalizar
from tests.fabricas import cabeceras, crear_centro, crear_empresa, crear_tipo, crear_usuario, crear_vehiculo

HOY = date.today()
CABECERA_VEHICULOS = ["Matrícula", "Tipo", "Centro", "Marca", "Modelo", "Año", "Capacidad", "Combustible", "Km"]


# --- Leer el archivo (sin base de datos) -------------------------------------


def xlsx(*filas: list[Any]) -> bytes:
    libro = Workbook()
    for fila in filas:
        libro.active.append(fila)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


@pytest.mark.parametrize(
    ("texto", "normalizado"),
    [("  Año * ", "ano"), ("MATRÍCULA", "matricula"), ("Mecánico/a", "mecanico/a"), ("Cochera  Central", "cochera central"), ("Fecha de alta:", "fecha de alta")],
)
def test_normalizar(texto: str, normalizado: str) -> None:
    assert normalizar(texto) == normalizado


def test_lee_un_excel_saltando_las_filas_vacias() -> None:
    cabecera, datos = leer_tabla(xlsx(["Nombre", "Puesto"], ["Ana", "Tráfico"], [None, None], ["Luis", "Otro"]), "personal.xlsx")

    assert cabecera == ["nombre", "puesto"]
    assert datos == [(2, ["Ana", "Tráfico"]), (4, ["Luis", "Otro"])]  # la fila 3 vacía se salta, pero se respeta la numeración


def test_lee_un_csv_de_excel_en_espanol() -> None:
    """Excel en español: separado por ";" y en Windows-1252 (las tildes no son UTF-8)."""
    contenido = "Nombre;Puesto\r\nAna Muñoz;Mecánico/a\r\n".encode("cp1252")

    cabecera, datos = leer_tabla(contenido, "PERSONAL.CSV")

    assert cabecera == ["nombre", "puesto"]
    assert datos == [(2, ["Ana Muñoz", "Mecánico/a"])]


def test_lee_un_csv_utf8_con_comas() -> None:
    contenido = "﻿Nombre,Puesto\nÁlvaro,Tráfico\n".encode()  # con BOM, como lo guardan muchos programas

    assert leer_tabla(contenido, "p.csv") == (["nombre", "puesto"], [(2, ["Álvaro", "Tráfico"])])


@pytest.mark.parametrize(
    ("contenido", "nombre", "mensaje"),
    [
        (b"x", "datos.xls", "Formato no admitido"),
        (b"esto no es un zip", "datos.xlsx", "No se ha podido leer"),
        (xlsx(), "vacio.xlsx", "está vacío"),
        (xlsx(["Nombre"]), "cabecera.xlsx", "solo tiene la cabecera"),
        (b"Nombre\n" + b"x\n" * 1001, "muchas.csv", "Demasiadas filas"),
        (b"x" * (2 * 1024 * 1024 + 1), "grande.csv", "demasiado grande"),
    ],
)
def test_archivos_que_no_se_pueden_importar(contenido: bytes, nombre: str, mensaje: str) -> None:
    with pytest.raises(ArchivoNoValido, match=mensaje):
        leer_tabla(contenido, nombre)


@pytest.mark.parametrize(("valor", "entero"), [(125000, 125000), (125000.0, 125000), ("125.000", 125000), ("125 000", 125000), (" 42 ", 42)])
def test_a_entero(valor: Any, entero: int) -> None:
    assert a_entero(valor) == entero


@pytest.mark.parametrize("valor", ["1,5", 1.5, "1.5", "12.34", "doce", True])
def test_a_entero_rechaza(valor: Any) -> None:
    with pytest.raises(ValueError, match="número entero"):
        a_entero(valor)


@pytest.mark.parametrize("valor", [datetime(2026, 3, 1, 0, 0), date(2026, 3, 1), "01/03/2026", "1/3/2026", "01-03-2026", "2026-03-01", "01/03/26"])
def test_a_fecha(valor: Any) -> None:
    assert a_fecha(valor) == date(2026, 3, 1)


def test_a_fecha_rechaza() -> None:
    with pytest.raises(ValueError, match="dd/mm/aaaa"):
        a_fecha("31/02/2026")


# --- Por la API --------------------------------------------------------------


@pytest.fixture
def e(db: Session) -> dict[str, Any]:
    empresa = crear_empresa(db)
    centro, tipo = crear_centro(db, empresa, "Cochera Central"), crear_tipo(db, empresa, "Autobús")
    plan = PlanMantenimiento(empresa_id=empresa.id, tipo_vehiculo_id=tipo.id, nombre="Mantenimiento A", intervalo_km=30_000, intervalo_dias=365)
    db.add(plan)
    db.flush()
    db.add(TareaPlan(empresa_id=empresa.id, plan_id=plan.id, orden=1, descripcion="Aceite"))
    db.flush()
    usuarios = {rol: cabeceras(crear_usuario(db, empresa, f"{rol}@example.com", rol)) for rol in RolUsuario}
    return {"db": db, "empresa": empresa, "centro": centro, "tipo": tipo, **usuarios}


def subir(api: TestClient, e: dict, que: str, contenido: bytes, nombre: str = "datos.xlsx", rol: RolUsuario = RolUsuario.TRAFICO) -> Any:
    return api.post(f"/importar/{que}", files={"archivo": (nombre, contenido)}, headers=e[rol])


def contar(db: Session, modelo: Any, empresa_id: int) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(modelo.empresa_id == empresa_id))


def plantilla(api: TestClient, e: dict, que: str) -> bytes:
    r = api.get(f"/importar/{que}/plantilla", headers=e[RolUsuario.TRAFICO])
    assert r.status_code == 200
    return r.content


def test_al_subir_la_plantilla_de_vehiculos_se_crean_los_registros(api: TestClient, e: dict) -> None:
    """Criterio literal de GEN-05 (parte 1), con vehículos."""
    r = subir(api, e, "vehiculos", plantilla(api, e, "vehiculos"))

    assert r.status_code == 201, r.text
    assert r.json() == {"importados": 2}
    vehiculos = list(e["db"].scalars(select(Vehiculo).where(Vehiculo.empresa_id == e["empresa"].id)))
    assert [(v.matricula, v.centro_id, v.tipo_id) for v in vehiculos] == [
        ("0001ZZZ", e["centro"].id, e["tipo"].id),
        ("0002ZZZ", e["centro"].id, e["tipo"].id),
    ]
    # Igual que un alta normal: con su lectura de km inicial y sus planes preventivos.
    assert contar(e["db"], LecturaKm, e["empresa"].id) == 2
    assert contar(e["db"], EstadoPlan, e["empresa"].id) == 2
    assert {v.km_actuales for v in vehiculos} == {125_000, 0}


def test_al_subir_la_plantilla_de_personal_se_crean_los_registros(api: TestClient, e: dict) -> None:
    """Criterio literal de GEN-05 (parte 1), con personas."""
    r = subir(api, e, "personas", plantilla(api, e, "personas"))

    assert r.status_code == 201, r.text
    personas = list(e["db"].scalars(select(Persona).where(Persona.empresa_id == e["empresa"].id).order_by(Persona.nombre)))
    assert [(p.nombre, p.puesto, p.fecha_alta) for p in personas] == [
        ("Persona Ejemplo Dos", "mecanico", HOY),
        ("Persona Ejemplo Uno", "conductor", HOY),
    ]


def test_la_plantilla_trae_instrucciones_con_los_valores_de_la_empresa(api: TestClient, e: dict) -> None:
    libro = load_workbook(BytesIO(plantilla(api, e, "vehiculos")))

    assert libro.sheetnames == ["Vehículos", "Instrucciones"]
    assert [c.value for c in libro["Vehículos"][1]] == CABECERA_VEHICULOS
    textos = [c.value for fila in libro["Instrucciones"].iter_rows() for c in fila]
    assert "Cochera Central" in textos and "Autobús" in textos


def test_las_filas_con_errores_se_listan_y_no_se_importa_nada(api: TestClient, e: dict) -> None:
    """Criterio literal de GEN-05 (parte 2): una fila buena + varias malas = 0 importadas."""
    crear_vehiculo(e["db"], e["empresa"], matricula="5555BBB")  # ya existe (de la empresa)
    antes = contar(e["db"], Vehiculo, e["empresa"].id)
    archivo = xlsx(
        CABECERA_VEHICULOS,
        ["1111AAA", "Autobús", "Cochera Central", "Irizar", "i6", 2020, 55, "Diésel", 300_000],  # 2: correcta
        ["2222AAA", "Tractor", "Cochera Central", "Volvo", "FH", 2019, None, "Diésel", 0],  # 3: tipo que no existe
        ["3333AAA", "Autobús", "Cochera Sur", "Volvo", "B8", 1900, None, "Carbón", 0],  # 4: centro, año y combustible
        ["5555 bbb", "Autobús", "Cochera Central", "Volvo", "B8", 2020, None, "Diésel", 0],  # 5: matrícula ya existe
        ["1111-AAA", "Autobús", "Cochera Central", "Volvo", "B8", 2020, None, "Diésel", 0],  # 6: repetida en el archivo
        ["6666AAA", "Autobús", "Cochera Central", None, "B8", 2020, None, "Diésel", "mucho"],  # 7: sin marca, km no numérico
    )

    r = subir(api, e, "vehiculos", archivo)

    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert detalle["mensaje"] == "No se ha importado nada: hay 5 filas con errores"
    errores = {(x["fila"], x["columna"]): x["motivo"] for x in detalle["errores"]}
    assert errores == {
        (3, "Tipo"): "«Tractor» no es ninguno de los tipos de vehículo de la empresa",
        (4, "Centro"): "«Cochera Sur» no es ninguno de los centros de la empresa",
        (4, "Combustible"): "«Carbón» no es un combustible admitido",
        (4, "Año"): f"El año debe estar entre 1950 y {HOY.year + 1}",  # todos los errores de la fila a la vez
        (5, "Matrícula"): "ya existe un vehículo con la matrícula 5555BBB",
        (6, "Matrícula"): "está repetida en el archivo (también en la fila 2)",
        (7, "Marca"): "es obligatorio",
        (7, "Km"): "debe ser un número entero (sin decimales)",
    }
    assert contar(e["db"], Vehiculo, e["empresa"].id) == antes  # ni siquiera la fila 2, que era correcta


def test_los_errores_de_los_esquemas_salen_en_espanol(api: TestClient, e: dict) -> None:
    archivo = xlsx(
        CABECERA_VEHICULOS,
        ["1111AAA", "Autobús", "Cochera Central", "Irizar", "i6", 1900, None, "Diésel", 0],
        ["1112AAA", "Autobús", "Cochera Central", "M" * 51, "i6", 2020, 0, "Diésel", 0],
        ["MAL!", "Autobús", "Cochera Central", "Irizar", "i6", 2020, None, "Diésel", -5],
    )

    errores = {(x["fila"], x["columna"]): x["motivo"] for x in subir(api, e, "vehiculos", archivo).json()["detail"]["errores"]}

    assert errores[(2, "Año")].startswith("El año debe estar entre 1950 y")
    assert errores[(3, "Marca")] == "es demasiado largo (máximo 50 caracteres)"
    assert errores[(3, "Capacidad")] == "debe ser mayor que 0"
    assert errores[(4, "Matrícula")] == "La matrícula solo puede tener letras y números (entre 2 y 15)"
    assert errores[(4, "Km")] == "no puede ser menor que 0"


def test_subir_dos_veces_la_misma_plantilla_no_duplica(api: TestClient, e: dict) -> None:
    contenido = plantilla(api, e, "vehiculos")
    assert subir(api, e, "vehiculos", contenido).status_code == 201

    r = subir(api, e, "vehiculos", contenido)

    assert r.status_code == 422
    assert [x["motivo"] for x in r.json()["detail"]["errores"]] == [
        "ya existe un vehículo con la matrícula 0001ZZZ",
        "ya existe un vehículo con la matrícula 0002ZZZ",
    ]


def test_un_csv_con_cabeceras_y_valores_escritos_a_mano(api: TestClient, e: dict) -> None:
    """Sin tildes ni mayúsculas en la cabecera, "diesel" en minúsculas, km con punto de miles."""
    contenido = "matricula;TIPO;centro;marca;modelo;ano;combustible;km\r\n1234 XYZ;autobus;cochera central;Irizar;i6;2020;diesel;125.000\r\n"

    r = subir(api, e, "vehiculos", contenido.encode("cp1252"), "flota.csv")

    assert r.status_code == 201, r.text
    v = e["db"].scalar(select(Vehiculo).where(Vehiculo.empresa_id == e["empresa"].id))
    assert (v.matricula, v.combustible, v.km_actuales, v.capacidad) == ("1234XYZ", "diesel", 125_000, None)


def test_personas_con_errores(api: TestClient, e: dict) -> None:
    archivo = xlsx(
        ["Nombre", "Puesto", "Centro", "Fecha de alta"],
        ["Ana", "Conductora", "Cochera Central", "01/03/2026"],  # "Conductora" vale (etiqueta sin "/a"… y con "a")
        ["Luis", "Piloto", "Cochera Central", "01/03/2026"],
        ["Eva", "Tráfico", "Cochera Central", "31/02/2026"],
    )

    r = subir(api, e, "personas", archivo)

    errores = {(x["fila"], x["columna"]): x["motivo"] for x in r.json()["detail"]["errores"]}
    assert errores == {
        (2, "Puesto"): "«Conductora» no es un puesto admitido",
        (3, "Puesto"): "«Piloto» no es un puesto admitido",
        (4, "Fecha de alta"): "no es una fecha válida (usa dd/mm/aaaa)",
    }
    assert contar(e["db"], Persona, e["empresa"].id) == 0


def test_faltan_columnas(api: TestClient, e: dict) -> None:
    r = subir(api, e, "vehiculos", xlsx(["Matrícula", "Marca"], ["1111AAA", "Irizar"]))

    assert r.status_code == 422
    assert r.json()["detail"]["mensaje"].startswith("Faltan columnas en la cabecera: Tipo, Centro, Modelo, Año, Combustible")


def test_un_archivo_que_no_es_excel(api: TestClient, e: dict) -> None:
    r = subir(api, e, "personas", b"%PDF-1.7", "personal.pdf")

    assert r.status_code == 422
    assert r.json()["detail"]["mensaje"] == "Formato no admitido: sube un Excel (.xlsx) o un CSV (.csv)"


def test_los_centros_de_otra_empresa_no_valen(api: TestClient, e: dict, db: Session) -> None:
    otra = crear_empresa(db, "Otra")
    crear_centro(db, otra, "Base Norte")

    r = subir(api, e, "personas", xlsx(["Nombre", "Puesto", "Centro", "Fecha de alta"], ["Ana", "Otro", "Base Norte", HOY]))

    assert r.json()["detail"]["errores"][0]["motivo"] == "«Base Norte» no es ninguno de los centros de la empresa"


@pytest.mark.parametrize("rol", [RolUsuario.TALLER, RolUsuario.CONDUCTOR])
def test_solo_gerente_y_trafico_importan(api: TestClient, e: dict, rol: RolUsuario) -> None:
    assert subir(api, e, "vehiculos", b"x", "a.csv", rol=rol).status_code == 403
    assert subir(api, e, "personas", b"x", "a.csv", rol=rol).status_code == 403
    assert api.get("/importar/vehiculos/plantilla", headers=e[rol]).status_code == 403
    assert subir(api, e, "personas", plantilla(api, e, "personas"), rol=RolUsuario.ADMIN).status_code == 201
