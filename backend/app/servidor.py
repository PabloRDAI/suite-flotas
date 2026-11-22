"""Servidor completo para Docker (demo local o despliegue): API y web en un solo proceso.

    /api/...   -> la API (app/main.py), igual que en desarrollo a través del proxy de Vite
    /...       -> el frontend compilado (frontend/dist)

Mismo origen para la web y la API: sin CORS y sin cambiar nada del frontend, que ya
llama a /api. En desarrollo no se usa: allí la API se arranca con app.main:app y la web
con Vite.

Arranque:  uvicorn app.servidor:app
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.config import get_settings
from app.main import app as api


class WebConRutasDeReact(StaticFiles):
    """Archivos de la web; una ruta que no es un archivo devuelve index.html.

    Así funcionan las URL de React Router al entrar directamente o al recargar
    (p. ej. /vehiculos/3 no es un archivo: lo resuelve React en el navegador).
    Lo que parece un archivo (/assets/x.js, /logo.png) y no existe sigue siendo 404.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response("index.html", scope)


def crear_servidor(carpeta_web: Path) -> FastAPI:
    servidor = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # la documentación, en /api/docs
    servidor.mount("/api", api)
    # check_dir=False: importar este módulo no falla si la web no está compilada (p. ej. en los tests).
    servidor.mount("/", WebConRutasDeReact(directory=carpeta_web, html=True, check_dir=False))
    return servidor


app = crear_servidor(get_settings().carpeta_web)
