"""Importar vehículos y personas desde Excel (.xlsx) o CSV (GEN-05).

Criterio: "Al subir la plantilla de ejemplo se crean los registros; las filas con errores
se listan con su motivo sin importar nada a medias."

Cómo se consigue el "nada a medias":
1. Se lee el archivo entero y se valida CADA fila (tipos, valores admitidos, centro y tipo
   de la empresa, matrícula libre y no repetida en el propio archivo…), acumulando errores.
2. Si hay algún error, se lanza ImportacionConErrores con la lista y no se toca la BD.
3. Si no hay ninguno, se crean todos los registros en la MISMA transacción (un solo commit,
   que hace quien llama): o entran todos, o ninguno.

Los motivos se escriben en español y con la columna y la fila tal como las ve la persona en
Excel (la fila 1 es la cabecera; los datos empiezan en la 2).
"""

import csv
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from io import BytesIO, StringIO
from typing import Any

from openpyxl import load_workbook
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Centro, Combustible, Persona, Puesto, TipoVehiculo, Vehiculo
from app.schemas import PersonaCrear, VehiculoCrear, normalizar_matricula
from app.servicios.etiquetas import ETIQUETAS
from app.servicios.excel import Columna, libro_varias_hojas
from app.servicios.vehiculos import alta_vehiculo

MAX_BYTES = 2 * 1024 * 1024  # 2 MB: de sobra para 1.000 filas
MAX_FILAS = 1000


class ArchivoNoValido(Exception):
    """El archivo no se puede leer o le faltan columnas: no se llega a mirar ninguna fila."""


@dataclass(frozen=True)
class ErrorFila:
    fila: int  # número de fila en Excel (1 = cabecera)
    columna: str | None
    motivo: str


class ImportacionConErrores(Exception):
    def __init__(self, errores: list[ErrorFila]) -> None:
        super().__init__(f"{len(errores)} errores")
        self.errores = errores


# --- Leer el archivo ---------------------------------------------------------


def normalizar(texto: Any) -> str:
    """Para comparar sin fijarse en mayúsculas, tildes, espacios de más, '*' ni ':'.

    "  Año * " -> "ano" · "Mecánico/a" -> "mecanico/a" · "Cochera  Central" -> "cochera central"
    """
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.lower().replace("*", " ").replace(":", " ").split())


def _vacia(fila: Sequence[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in fila)


def _leer_xlsx(contenido: bytes) -> Iterable[tuple[int, Sequence[Any]]]:
    libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    # Los datos van en la primera hoja (la plantilla trae las instrucciones en la segunda).
    return list(enumerate(libro.worksheets[0].iter_rows(values_only=True), start=1))


def _leer_csv(contenido: bytes) -> Iterable[tuple[int, Sequence[Any]]]:
    # Excel en español guarda los CSV en Windows-1252 y separados por ";"; otros programas, en UTF-8 y con ",".
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("cp1252")
    try:
        dialecto: Any = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
    except csv.Error:
        dialecto = "excel"
    lector = csv.reader(StringIO(texto), dialecto)
    return [(lector.line_num, fila) for fila in lector]


def leer_tabla(contenido: bytes, nombre_archivo: str) -> tuple[list[str], list[tuple[int, list[Any]]]]:
    """Devuelve (cabecera normalizada, filas con su número de fila). Se saltan las filas vacías."""
    if len(contenido) > MAX_BYTES:
        raise ArchivoNoValido("El archivo es demasiado grande (máximo 2 MB)")
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""
    if extension not in {"xlsx", "csv"}:
        raise ArchivoNoValido("Formato no admitido: sube un Excel (.xlsx) o un CSV (.csv)")
    try:
        filas = _leer_xlsx(contenido) if extension == "xlsx" else _leer_csv(contenido)
    except Exception as error:  # zip roto, no es un Excel, codificación imposible…
        raise ArchivoNoValido(f"No se ha podido leer el archivo como {extension.upper()}") from error

    con_datos = [(n, list(f)) for n, f in filas if not _vacia(f)]
    if not con_datos:
        raise ArchivoNoValido("El archivo está vacío")
    (_, cabecera), datos = con_datos[0], con_datos[1:]
    if not datos:
        raise ArchivoNoValido("El archivo solo tiene la cabecera: no hay filas que importar")
    if len(datos) > MAX_FILAS:
        raise ArchivoNoValido(f"Demasiadas filas ({len(datos)}): el máximo es {MAX_FILAS} por archivo")
    return [normalizar(c) if c is not None else "" for c in cabecera], datos


# --- Convertir cada celda ----------------------------------------------------


def a_texto(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)  # Excel guarda "500" como 500.0
    texto = str(valor).strip()
    return texto or None


def a_entero(valor: Any) -> int:
    if isinstance(valor, bool):
        raise ValueError("debe ser un número entero")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if valor.is_integer():
            return int(valor)
        raise ValueError("debe ser un número entero (sin decimales)")
    texto = str(valor).strip().replace(" ", "")  # "125 000" -> "125000"
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", texto):  # punto de miles: "125.000" (pero "1.5" no)
        texto = texto.replace(".", "")
    if re.fullmatch(r"-?\d+", texto):
        return int(texto)
    raise ValueError("debe ser un número entero (sin decimales)")


def a_fecha(valor: Any) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    raise ValueError("no es una fecha válida (usa dd/mm/aaaa)")


def opciones_de(enum: type[StrEnum]) -> dict[str, str]:
    """Textos admitidos para un valor: el interno ("mecanico"), la etiqueta ("Mecánico/a") y
    la etiqueta sin "/a" ("Mecánico"), sin fijarse en mayúsculas ni tildes."""
    opciones: dict[str, str] = {}
    for valor in enum:
        etiqueta = ETIQUETAS[enum][valor.value]
        for texto in (valor.value, etiqueta, etiqueta.removesuffix("/a")):
            opciones[normalizar(texto)] = valor.value
    return opciones


def a_opcion(opciones: dict[str, Any], que: str) -> Callable[[Any], Any]:
    def convertir(valor: Any) -> Any:
        try:
            return opciones[normalizar(valor)]
        except KeyError:
            raise ValueError(f"«{valor}» no es {que}") from None

    return convertir


# Mensajes de Pydantic en español (los propios ya lo están: "La matrícula solo puede…").
_MENSAJES = {
    "string_too_long": "es demasiado largo (máximo {max_length} caracteres)",
    "greater_than": "debe ser mayor que {gt}",
    "greater_than_equal": "no puede ser menor que {ge}",
    "less_than_equal": "no puede ser mayor que {le}",
    "missing": "es obligatorio",
}


def _motivo_pydantic(error: Any) -> str:
    if error["type"] == "value_error":
        return str(error["ctx"]["error"])
    return _MENSAJES.get(error["type"], error["msg"]).format(**error.get("ctx", {}))


# --- Columnas de cada importación --------------------------------------------


@dataclass(frozen=True)
class Campo:
    titulo: str  # como aparece en la plantilla
    clave: str  # campo del esquema de alta
    obligatorio: bool
    ayuda: str  # para la hoja de instrucciones
    convertir: Callable[[Any], Any] = a_texto


def _validar(
    cabecera: list[str],
    datos: list[tuple[int, list[Any]]],
    campos: Sequence[Campo],
    esquema: type[BaseModel],
    comprobar: Callable[[int, dict[str, Any]], list[ErrorFila]],
) -> tuple[list[BaseModel], list[ErrorFila]]:
    """Convierte y valida todas las filas; devuelve los registros válidos y TODOS los errores."""
    posicion = {campo.clave: cabecera.index(normalizar(campo.titulo)) for campo in campos if normalizar(campo.titulo) in cabecera}
    faltan = [c.titulo for c in campos if c.obligatorio and c.clave not in posicion]
    if faltan:
        raise ArchivoNoValido(f"Faltan columnas en la cabecera: {', '.join(faltan)} (descarga la plantilla para ver el formato)")

    titulos = {c.clave: c.titulo for c in campos}
    registros: list[BaseModel] = []
    errores: list[ErrorFila] = []
    for n, fila in datos:
        valores: dict[str, Any] = {}
        errores_fila: list[ErrorFila] = []
        for campo in campos:
            crudo = fila[posicion[campo.clave]] if campo.clave in posicion and posicion[campo.clave] < len(fila) else None
            if a_texto(crudo) is None:
                if campo.obligatorio:
                    errores_fila.append(ErrorFila(n, campo.titulo, "es obligatorio"))
                continue
            try:
                valores[campo.clave] = campo.convertir(crudo)
            except ValueError as error:
                errores_fila.append(ErrorFila(n, campo.titulo, str(error)))
        errores_fila += comprobar(n, valores)
        # Se valida con el esquema aunque ya haya errores: así salen TODOS los de la fila a la vez
        # (sin repetir el de una columna que ya tiene el suyo, p. ej. "es obligatorio").
        try:
            registro = esquema(**valores)
        except ValidationError as error:
            con_error = {e.columna for e in errores_fila}
            for e in error.errors():
                columna = titulos.get(str(e["loc"][0])) if e["loc"] else None
                if columna is None or columna not in con_error:
                    errores_fila.append(ErrorFila(n, columna, _motivo_pydantic(e)))
        else:
            if not errores_fila:
                registros.append(registro)
        errores += errores_fila
    return registros, errores


def _nombres(db: Session, modelo: type[Centro] | type[TipoVehiculo], empresa_id: int) -> dict[str, int]:
    """{nombre normalizado: id} de los centros o tipos activos de la empresa."""
    consulta = select(modelo.id, modelo.nombre).where(modelo.empresa_id == empresa_id, modelo.activo)
    return {normalizar(nombre): id_ for id_, nombre in db.execute(consulta).tuples().all()}


# --- Vehículos ---------------------------------------------------------------


def campos_vehiculo(centros: dict[str, int], tipos: dict[str, int]) -> list[Campo]:
    return [
        Campo("Matrícula", "matricula", True, "Sin espacios ni guiones, o con ellos: 1234 ABC = 1234ABC. No puede existir ya."),
        Campo("Tipo", "tipo_id", True, "Uno de los tipos de vehículo de la empresa (ver abajo).", a_opcion(tipos, "ninguno de los tipos de vehículo de la empresa")),
        Campo("Centro", "centro_id", True, "Uno de los centros de la empresa (ver abajo).", a_opcion(centros, "ninguno de los centros de la empresa")),
        Campo("Marca", "marca", True, "Texto, hasta 50 caracteres."),
        Campo("Modelo", "modelo", True, "Texto, hasta 80 caracteres."),
        Campo("Año", "anio", True, "Año de matriculación, p. ej. 2021.", a_entero),
        Campo("Capacidad", "capacidad", False, "Plazas o kg, según el tipo. Opcional.", a_entero),
        Campo("Combustible", "combustible", True, "Diésel, Gasolina, Eléctrico, Híbrido, GNC, GNL, GLP, Hidrógeno u Otro.", a_opcion(opciones_de(Combustible), "un combustible admitido")),
        Campo("Km", "km_actuales", False, "Km actuales, número entero. Si se deja vacío, 0.", a_entero),
    ]


def validar_vehiculos(db: Session, empresa_id: int, contenido: bytes, nombre_archivo: str) -> list[VehiculoCrear]:
    """Lee y valida el archivo. Lanza ArchivoNoValido o ImportacionConErrores; si no, devuelve las altas."""
    cabecera, datos = leer_tabla(contenido, nombre_archivo)
    existentes = set(db.scalars(select(Vehiculo.matricula).where(Vehiculo.empresa_id == empresa_id)))
    vistas: dict[str, int] = {}  # matrícula -> fila donde apareció por primera vez

    def comprobar(n: int, valores: dict[str, Any]) -> list[ErrorFila]:
        if "matricula" not in valores:
            return []  # ya tiene su error: "es obligatorio"
        try:
            matricula = normalizar_matricula(valores["matricula"])
        except ValueError:
            return []  # el mensaje lo dará la validación del esquema
        if matricula in existentes:
            return [ErrorFila(n, "Matrícula", f"ya existe un vehículo con la matrícula {matricula}")]
        if matricula in vistas:
            return [ErrorFila(n, "Matrícula", f"está repetida en el archivo (también en la fila {vistas[matricula]})")]
        vistas[matricula] = n
        return []

    campos = campos_vehiculo(_nombres(db, Centro, empresa_id), _nombres(db, TipoVehiculo, empresa_id))
    registros, errores = _validar(cabecera, datos, campos, VehiculoCrear, comprobar)
    if errores:
        raise ImportacionConErrores(errores)
    return registros  # type: ignore[return-value]


def importar_vehiculos(db: Session, empresa_id: int, usuario_id: int, contenido: bytes, nombre_archivo: str, hoy: date) -> int:
    """GEN-05: todos o ninguno. Sin commit (lo hace quien llama, una sola vez)."""
    altas = validar_vehiculos(db, empresa_id, contenido, nombre_archivo)
    for datos in altas:
        alta_vehiculo(db, empresa_id, usuario_id, datos, hoy)
    return len(altas)


# --- Personas ----------------------------------------------------------------


def campos_persona(centros: dict[str, int]) -> list[Campo]:
    return [
        Campo("Nombre", "nombre", True, "Nombre y apellidos, hasta 150 caracteres. Sin DNI ni otros datos personales."),
        Campo("Puesto", "puesto", True, "Conductor/a, Mecánico/a, Tráfico u Otro.", a_opcion(opciones_de(Puesto), "un puesto admitido")),
        Campo("Centro", "centro_id", True, "Uno de los centros de la empresa (ver abajo).", a_opcion(centros, "ninguno de los centros de la empresa")),
        Campo("Fecha de alta", "fecha_alta", True, "Fecha dd/mm/aaaa.", a_fecha),
    ]


def importar_personas(db: Session, empresa_id: int, contenido: bytes, nombre_archivo: str) -> int:
    """GEN-05: todos o ninguno. Sin commit (lo hace quien llama, una sola vez)."""
    cabecera, datos = leer_tabla(contenido, nombre_archivo)
    registros, errores = _validar(cabecera, datos, campos_persona(_nombres(db, Centro, empresa_id)), PersonaCrear, lambda n, v: [])
    if errores:
        raise ImportacionConErrores(errores)
    db.add_all(Persona(empresa_id=empresa_id, **r.model_dump()) for r in registros)
    db.flush()
    return len(registros)


# --- Plantillas --------------------------------------------------------------


def _instrucciones(campos: Sequence[Campo], listas: dict[str, Iterable[str]]) -> list[tuple[str, list[Columna], list[list[Any]]]]:
    filas: list[list[Any]] = [[c.titulo, "Sí" if c.obligatorio else "No", c.ayuda] for c in campos]
    for titulo, valores in listas.items():
        filas += [["", "", ""], [titulo, "", ""]] + [["", "", v] for v in valores]
    filas += [["", "", ""], ["Notas", "", "La primera fila es la cabecera. Se importa todo o nada: si una fila tiene un error, no se crea ninguna."]]
    return [("Instrucciones", [Columna("Columna", 18), Columna("¿Obligatoria?", 13), Columna("Qué poner", 90)], filas)]


def plantilla_vehiculos(db: Session, empresa_id: int, hoy: date) -> bytes:
    """Plantilla con 2 filas de ejemplo que se pueden importar tal cual (con un centro y un tipo de la empresa)."""
    centros = [n for (n,) in db.execute(select(Centro.nombre).where(Centro.empresa_id == empresa_id, Centro.activo).order_by(Centro.nombre))]
    tipos = [n for (n,) in db.execute(select(TipoVehiculo.nombre).where(TipoVehiculo.empresa_id == empresa_id, TipoVehiculo.activo).order_by(TipoVehiculo.nombre))]
    usadas = set(db.scalars(select(Vehiculo.matricula).where(Vehiculo.empresa_id == empresa_id)))
    libres = (m for m in (f"{i:04d}ZZZ" for i in range(1, 10_000)) if m not in usadas)  # matrículas de ejemplo libres
    centro, tipo = (centros or ["(nombre de un centro)"])[0], (tipos or ["(nombre de un tipo)"])[0]
    ejemplos = [
        [next(libres), tipo, centro, "Marca de ejemplo", "Modelo A", hoy.year - 2, 55, "Diésel", 125_000],
        [next(libres), tipo, centro, "Marca de ejemplo", "Modelo B", hoy.year, None, "Eléctrico", 0],
    ]
    campos = campos_vehiculo({}, {})
    formatos = {"anio": "anio", "capacidad": "entero", "km_actuales": "entero"}
    columnas = [Columna(c.titulo, 16, formatos.get(c.clave, "texto")) for c in campos]
    return libro_varias_hojas(
        [("Vehículos", columnas, ejemplos), *_instrucciones(campos, {"Tipos de la empresa": tipos, "Centros de la empresa": centros})]
    )


def plantilla_personas(db: Session, empresa_id: int, hoy: date) -> bytes:
    centros = [n for (n,) in db.execute(select(Centro.nombre).where(Centro.empresa_id == empresa_id, Centro.activo).order_by(Centro.nombre))]
    centro = (centros or ["(nombre de un centro)"])[0]
    ejemplos = [
        ["Persona Ejemplo Uno", "Conductor/a", centro, hoy],
        ["Persona Ejemplo Dos", "Mecánico/a", centro, hoy],
    ]
    campos = campos_persona({})
    columnas = [Columna("Nombre", 30), Columna("Puesto", 14), Columna("Centro", 22), Columna("Fecha de alta", 14, "fecha")]
    return libro_varias_hojas([("Personal", columnas, ejemplos), *_instrucciones(campos, {"Centros de la empresa": centros})])
