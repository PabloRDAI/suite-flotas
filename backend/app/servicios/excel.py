"""Escribir listados en Excel (.xlsx) para descargarlos (GEN-06).

Cada listado define sus columnas (título, ancho y formato) y pasa sus filas; aquí se
da el formato común: cabecera en negrita fija al hacer scroll, autofiltro, fechas
dd/mm/aaaa y euros con 2 decimales.

Seguridad: un texto que empieza por "=" se guardaría como FÓRMULA (openpyxl lo hace
así) y Excel la ejecutaría al abrir el archivo: "inyección de fórmulas". Todo texto
se fuerza a texto, de modo que "=HIPERVINCULO(...)" en una descripción se ve tal cual.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import Response
from openpyxl import Workbook
from openpyxl.cell.cell import TYPE_STRING
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Las fechas y horas se guardan en UTC; en el Excel, en hora de España (como en la aplicación).
ZONA = ZoneInfo("Europe/Madrid")

FORMATOS = {
    "fecha": "DD/MM/YYYY",
    "fecha_hora": "DD/MM/YYYY HH:MM",
    "euros": '#,##0.00" €"',
    "entero": "#,##0",
    "anio": "0",  # sin separador de miles: 2021, no 2.021
    "decimal": "#,##0.00",
    "euros_km": '#,##0.000" €/km"',  # coste por km
    "texto": "@",
}


@dataclass(frozen=True)
class Columna:
    titulo: str
    ancho: int = 14
    formato: str = "texto"  # una clave de FORMATOS


Valor = str | int | float | Decimal | date | datetime | None


def _celda(valor: Valor) -> Valor:
    if isinstance(valor, datetime):
        # openpyxl no admite fechas con zona horaria: se pasa a hora de España y se quita la zona.
        return valor.astimezone(ZONA).replace(tzinfo=None) if valor.tzinfo else valor
    return valor


Hoja = tuple[str, Sequence[Columna], Iterable[Sequence[Valor]]]  # (nombre, columnas, filas)


def _escribir_hoja(ws, columnas: Sequence[Columna], filas: Iterable[Sequence[Valor]]) -> None:  # type: ignore[no-untyped-def]
    ws.append([c.titulo for c in columnas])
    for celda in ws[1]:
        celda.font = Font(bold=True)
        celda.fill = PatternFill("solid", fgColor="E9ECEF")
    for fila in filas:
        ws.append([_celda(v) for v in fila])
        for celda, columna in zip(ws[ws.max_row], columnas, strict=True):
            if isinstance(celda.value, str):
                celda.data_type = TYPE_STRING  # nunca fórmula (ver docstring del módulo)
            elif celda.value is not None:
                celda.number_format = FORMATOS[columna.formato]
    for i, columna in enumerate(columnas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = columna.ancho
    ws.freeze_panes = "A2"  # la cabecera queda fija al bajar
    ws.auto_filter.ref = ws.dimensions  # flechas de filtro en la cabecera


def libro_varias_hojas(hojas: Sequence[Hoja]) -> bytes:
    """Un libro con varias hojas (p. ej. la plantilla de importación y sus instrucciones)."""
    libro = Workbook()
    libro.remove(libro.active)
    for nombre, columnas, filas in hojas:
        _escribir_hoja(libro.create_sheet(nombre[:31]), columnas, filas)  # Excel: máx. 31 caracteres
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def libro_xlsx(hoja: str, columnas: Sequence[Columna], filas: Iterable[Sequence[Valor]]) -> bytes:
    """Un libro de una hoja con cabecera y filas. Devuelve el archivo en bytes."""
    return libro_varias_hojas([(hoja, columnas, filas)])


def respuesta_xlsx(contenido: bytes, nombre: str) -> Response:
    """Respuesta de descarga: el navegador lo guarda como "<nombre>-AAAA-MM-DD.xlsx"."""
    archivo = f"{nombre}-{date.today().isoformat()}.xlsx"
    return Response(contenido, media_type=TIPO_XLSX, headers={"Content-Disposition": f'attachment; filename="{archivo}"'})


def si_no(valor: bool) -> str:
    return "Sí" if valor else "No"
