"""Panel de flota (FLO-04)."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Response, status

from app.deps import Db, UsuarioActual
from app.schemas import IndicadoresSalida, PanelSalida
from app.servicios.excel import Columna, libro_xlsx, respuesta_xlsx
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


@router.get("/indicadores/exportar")
def exportar_indicadores(
    usuario: UsuarioActual,
    db: Db,
    desde: date | None = None,
    hasta: date | None = None,
    centro_id: int | None = None,
    tipo_id: int | None = None,
) -> Response:
    """GEN-06: la tabla de costes por vehículo (MAN-08) en Excel, con el periodo y los filtros del panel."""
    datos = indicadores(usuario, db, desde, hasta, centro_id, tipo_id)
    columnas = [
        Columna("Matrícula", 12), Columna("Coste", 12, "euros"), Columna("Km recorridos", 14, "entero"),
        Columna("Coste por km", 13, "euros_km"), Columna("Averías", 9, "entero"), Columna("Días parado", 12, "entero"),
        Columna("OT preventivas", 14, "entero"), Columna("OT correctivas", 14, "entero"),
    ]
    filas = [
        [v.matricula, v.coste, v.km_recorridos, v.coste_por_km, v.averias, v.dias_inmovilizado, v.ot_preventivas, v.ot_correctivas]
        for v in datos.vehiculos
    ]
    nombre_hoja = f"Del {datos.desde:%d-%m-%Y} al {datos.hasta:%d-%m-%Y}"
    return respuesta_xlsx(libro_xlsx(nombre_hoja, columnas, filas), "costes-por-vehiculo")
