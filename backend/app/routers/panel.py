"""Panel de flota (FLO-04)."""

from datetime import date

from fastapi import APIRouter

from app.deps import Db, UsuarioActual
from app.schemas import PanelSalida
from app.servicios.panel import calcular_panel

router = APIRouter(prefix="/panel", tags=["panel"])


@router.get("")
def panel(usuario: UsuarioActual, db: Db, centro_id: int | None = None, tipo_id: int | None = None) -> PanelSalida:
    """Contadores por estado, vehículos con su aptitud y alertas de la empresa del usuario.

    Filtros opcionales ?centro_id=… y ?tipo_id=…; los contadores reflejan el filtro.
    """
    return calcular_panel(db, usuario.empresa_id, date.today(), centro_id=centro_id, tipo_id=tipo_id)
