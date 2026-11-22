"""Importar vehículos y personal desde Excel o CSV (GEN-05).

- GET  /importar/{vehiculos|personas}/plantilla: plantilla .xlsx con 2 filas de ejemplo que
  se pueden importar tal cual, y una hoja de instrucciones con los valores admitidos.
- POST /importar/{vehiculos|personas}: sube el archivo (campo "archivo"). Todo o nada:
    201 {"importados": N}, o
    422 {"detail": {"mensaje": …, "errores": [{"fila", "columna", "motivo"}, …]}} sin crear nada.
- Solo gerente y tráfico (los mismos que pueden dar de alta vehículos y personas).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError

from app.deps import Db, GestionFlota, GestionPersonal
from app.schemas import ImportacionSalida
from app.servicios import importacion
from app.servicios.excel import TIPO_XLSX

router = APIRouter(prefix="/importar", tags=["importación"])

Archivo = Annotated[UploadFile, File(description="Excel (.xlsx) o CSV (.csv), con la cabecera de la plantilla")]


def _leer(archivo: UploadFile) -> bytes:
    return archivo.file.read(importacion.MAX_BYTES + 1)  # +1: para saber si se pasa del límite


def _ejecutar(db: Db, importar) -> ImportacionSalida:  # type: ignore[no-untyped-def]
    """Ejecuta la importación y traduce sus errores a respuestas HTTP. Un solo commit al final.

    Con errores de validación no hace falta deshacer nada: se valida TODO antes de escribir.
    """
    try:
        importados = importar()
    except importacion.ArchivoNoValido as error:
        detalle = {"mensaje": str(error), "errores": [{"fila": None, "columna": None, "motivo": str(error)}]}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detalle) from error
    except importacion.ImportacionConErrores as error:
        filas = len({e.fila for e in error.errores})
        detalle = {
            "mensaje": f"No se ha importado nada: {'hay 1 fila' if filas == 1 else f'hay {filas} filas'} con errores",
            "errores": [{"fila": e.fila, "columna": e.columna, "motivo": e.motivo} for e in error.errores],
        }
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detalle) from error
    except IntegrityError as error:  # alguien dio de alta la misma matrícula mientras tanto
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Otro usuario ha cambiado los datos a la vez: vuelve a intentarlo") from error
    try:
        db.commit()
    except IntegrityError as error:  # (lo mismo, si lo detecta la BD al confirmar)
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Otro usuario ha cambiado los datos a la vez: vuelve a intentarlo") from error
    return ImportacionSalida(importados=importados)


def _plantilla(contenido: bytes, nombre: str) -> Response:
    return Response(contenido, media_type=TIPO_XLSX, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/vehiculos/plantilla")
def plantilla_vehiculos(usuario: GestionFlota, db: Db) -> Response:
    return _plantilla(importacion.plantilla_vehiculos(db, usuario.empresa_id, date.today()), "plantilla-vehiculos.xlsx")


@router.post("/vehiculos", status_code=status.HTTP_201_CREATED)
def importar_vehiculos(archivo: Archivo, usuario: GestionFlota, db: Db) -> ImportacionSalida:
    contenido = _leer(archivo)
    return _ejecutar(
        db,
        lambda: importacion.importar_vehiculos(db, usuario.empresa_id, usuario.id, contenido, archivo.filename or "", date.today()),
    )


@router.get("/personas/plantilla")
def plantilla_personas(usuario: GestionPersonal, db: Db) -> Response:
    return _plantilla(importacion.plantilla_personas(db, usuario.empresa_id, date.today()), "plantilla-personal.xlsx")


@router.post("/personas", status_code=status.HTTP_201_CREATED)
def importar_personas(archivo: Archivo, usuario: GestionPersonal, db: Db) -> ImportacionSalida:
    contenido = _leer(archivo)
    return _ejecutar(db, lambda: importacion.importar_personas(db, usuario.empresa_id, contenido, archivo.filename or ""))
