"""Guardar y servir archivos subidos (fotos de averías, MAN-03), con seguridad.

- El TIPO se comprueba por los primeros bytes del archivo ("firma"), no por la
  extensión ni por lo que dice el navegador: ambas cosas se pueden falsificar.
- El TAMAÑO se limita leyendo como máximo el límite + 1 byte.
- El NOMBRE se genera al azar: nunca se usa el del usuario (podría contener
  rutas como "../../" para escribir fuera de la carpeta).
"""

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings


class AdjuntoNoValido(ValueError):
    """El archivo no es una imagen admitida o es demasiado grande."""

    def __init__(self, mensaje: str, demasiado_grande: bool = False) -> None:
        super().__init__(mensaje)
        self.demasiado_grande = demasiado_grande


# Formatos admitidos: extensión -> tipo MIME.
TIPOS = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_NOMBRE_VALIDO = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


def _extension_por_firma(cabecera: bytes) -> str | None:
    """Identifica el formato por su "firma" (los primeros bytes del archivo)."""
    if cabecera.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return ".webp"
    return None


def guardar_foto(archivo: UploadFile) -> str:
    """Valida y guarda la foto. Devuelve el nombre (aleatorio) con el que se guardó."""
    ajustes = get_settings()
    limite = ajustes.max_foto_mb * 1024 * 1024
    datos = archivo.file.read(limite + 1)
    if len(datos) > limite:
        raise AdjuntoNoValido(f"La foto supera los {ajustes.max_foto_mb} MB", demasiado_grande=True)
    if not datos:
        raise AdjuntoNoValido("La foto está vacía")
    extension = _extension_por_firma(datos[:12])
    if extension is None:
        raise AdjuntoNoValido("La foto debe ser una imagen JPEG, PNG o WebP")

    nombre = f"{uuid.uuid4().hex}{extension}"
    ajustes.carpeta_adjuntos.mkdir(parents=True, exist_ok=True)
    (ajustes.carpeta_adjuntos / nombre).write_bytes(datos)
    return nombre


def ruta_foto(nombre: str) -> Path:
    """Ruta en disco de una foto guardada. Solo acepta nombres generados por guardar_foto."""
    if not _NOMBRE_VALIDO.match(nombre):
        raise AdjuntoNoValido("Nombre de archivo no válido")
    return get_settings().carpeta_adjuntos / nombre


def tipo_mime(nombre: str) -> str:
    return TIPOS[Path(nombre).suffix]


def borrar_foto(nombre: str) -> None:
    """Borra una foto (p. ej. si al final no se pudo guardar la avería)."""
    ruta_foto(nombre).unlink(missing_ok=True)
