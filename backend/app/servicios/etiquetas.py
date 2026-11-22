"""Textos en español de los valores internos ("en_taller" -> "En taller").

Para lo que lee una persona fuera de la aplicación (Excel exportado) y para entender
lo que escribe al importar. Los mismos textos que muestra el frontend.
"""

from enum import StrEnum

from app.models import Combustible, Puesto
from app.reglas.estado_vehiculo import EstadoAveria, EstadoOT, EstadoVehiculo, GravedadAveria
from app.reglas.ordenes import OrigenOT, TipoOT
from app.reglas.preventivo import Situacion
from app.reglas.vencimientos import Semaforo

ETIQUETAS: dict[type[StrEnum], dict[str, str]] = {
    EstadoVehiculo: {"operativo": "Operativo", "en_taller": "En taller", "inmovilizado": "Inmovilizado", "baja": "De baja"},
    Combustible: {
        "diesel": "Diésel", "gasolina": "Gasolina", "electrico": "Eléctrico", "hibrido": "Híbrido", "gnc": "GNC",
        "gnl": "GNL", "glp": "GLP", "hidrogeno": "Hidrógeno", "otro": "Otro",
    },
    Puesto: {"conductor": "Conductor/a", "mecanico": "Mecánico/a", "trafico": "Tráfico", "otro": "Otro"},
    Semaforo: {"verde": "En regla", "ambar": "Caduca pronto", "rojo": "Caducada"},
    GravedadAveria: {"leve": "Leve", "grave": "Grave", "inmoviliza": "Inmoviliza"},
    EstadoAveria: {"comunicada": "Comunicada", "en_reparacion": "En reparación", "resuelta": "Resuelta"},
    EstadoOT: {"abierta": "Abierta", "en_curso": "En curso", "cerrada": "Cerrada", "cancelada": "Cancelada"},
    TipoOT: {"preventiva": "Preventiva", "correctiva": "Correctiva"},
    OrigenOT: {"plan": "Plan preventivo", "averia": "Avería", "manual": "Manual"},
    Situacion: {"al_dia": "Al día", "proximo": "Próximo", "vencido": "Vencido"},
}


def etiqueta(valor: StrEnum) -> str:
    return ETIQUETAS[type(valor)][valor.value]
