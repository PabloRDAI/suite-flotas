"""Punto de entrada de la API."""

from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routers import (
    auth,
    centros,
    lecturas_km,
    panel,
    tipos_vehiculo,
    tipos_vencimiento,
    vehiculos,
    vencimientos,
)

app = FastAPI(title=get_settings().nombre_app, version="0.1.0")

app.include_router(auth.router)
app.include_router(panel.router)
app.include_router(centros.router)
app.include_router(tipos_vehiculo.router)
app.include_router(tipos_vencimiento.router)
app.include_router(vehiculos.router)
app.include_router(lecturas_km.router)
app.include_router(vencimientos.router)


@app.get("/salud", tags=["sistema"])
def salud(response: Response, db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Comprueba que la API está viva y que puede hablar con la base de datos.

    - 200 si todo va bien.
    - 503 (servicio no disponible) si la base de datos no responde.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"estado": "error", "base_de_datos": "sin conexión"}
    return {"estado": "ok", "base_de_datos": "ok"}
