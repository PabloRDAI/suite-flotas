"""Panel de flota (FLO-04)."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status

from app.deps import Db, UsuarioActual
from app.schemas import IndicadoresSalida, PanelSalida
from app.servicios.indicadores import calcular_indicadores
from app.servicios.panel import calcular_panel

router = APIRouter(prefix="/panel", tags=["panel"])


@router.get("")
def panel(usuario: UsuarioActual, db: Db, centro_id: int | None = None, tipo_id: int | None = None) -> PanelSalida:
    """Contadores por estado, vehículos con su aptitud y alertas de la empresa del usuario.

    Filtros opcionales ?centro_id=… y ?tipo_id=…; los contadores reflejan el filtro.
    """
    return calcular_panel(db, usuario.empresa_id, date.today(), centro_id=centro_id, tipo_id=tipo_id)


# Periodo por defecto de los indicadores: los últimos 6 meses.
DIAS_POR_DEFECTO = 182


@router.get("/indicadores")
def indicadores(
    usuario: UsuarioActual,
    db: Db,
    desde: date | None = None,
    hasta: date | None = None,
    centro_id: int | None = None,
    tipo_id: int | None = None,
) -> IndicadoresSalida:
    """MAN-08: coste por vehículo y por km, averías, días de inmovilización y % de preventivo.

    Periodo: ?desde=…&hasta=… (por defecto, los últimos 6 meses hasta hoy). Filtros por centro y tipo.
    """
    hoy = date.today()
    hasta = hasta or hoy
    desde = desde or hasta - timedelta(days=DIAS_POR_DEFECTO)
    if desde > hasta:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha de inicio no puede ser posterior a la de fin")
    return calcular_indicadores(db, usuario.empresa_id, desde, hasta, hoy, centro_id=centro_id, tipo_id=tipo_id)
