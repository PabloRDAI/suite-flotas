"""Empresa de demostración con datos ficticios (GEN-04).

Dos piezas:
- planificar_demo(): Python puro. Decide QUÉ datos crear, con una semilla fija:
  cada ejecución genera exactamente los mismos datos (reproducible y testeable).
- crear_empresa_demo(): guarda el plan en la base de datos.

Todo es inventado: nombre de empresa, marcas, matrículas y emails
(@demo.example.com, dominio reservado para ejemplos). Las fechas son relativas a
"hoy", así que siempre hay vencimientos en rojo y en ámbar para enseñar.

Incluye 30 personas con su documentación (PER-01, PER-02) y sus asignaciones a
vehículos con historial (PER-03), planes de mantenimiento preventivo con su estado
en cada vehículo (MAN-01), averías comunicadas (MAN-03) y 6 meses de historial
de órdenes de trabajo con sus costes (MAN-04 a MAN-06): todo lo que pide GEN-04.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    AplicaA,
    Asignacion,
    Averia,
    Centro,
    Combustible,
    Empresa,
    EstadoPlan,
    LecturaKm,
    LineaOT,
    OrdenTrabajo,
    Persona,
    PlanMantenimiento,
    Puesto,
    Recambio,
    RolUsuario,
    TareaPlan,
    TipoCentro,
    TipoVehiculo,
    TipoVencimiento,
    UnidadCapacidad,
    Usuario,
    Vehiculo,
    Vencimiento,
)
from app.reglas.asignaciones import avisos_de_documentacion
from app.reglas.estado_vehiculo import EstadoAveria, EstadoOT, GravedadAveria
from app.reglas.ordenes import Concepto, Linea, OrigenOT, TipoOT, coste
from app.reglas.preventivo import Situacion, calcular_proximo, evaluar
from app.reglas.vencimientos import Documento, Semaforo, aptitud_para_salir, semaforo, vigentes
from app.seguridad import hash_password
from app.servicios.adjuntos import borrar_foto
from app.servicios.estado_vehiculo import actualizar_estado
from app.servicios.preventivos import recalcular

NOMBRE_EMPRESA = "Transportes Demo (ficticia)"
DOMINIO = "demo.example.com"
PASSWORD_DEMO = "demostracion"  # solo para la demo local; nunca para datos reales
SEMILLA = 2026
DIAS_DE_HISTORIAL = 182  # unos 6 meses

CENTROS = [
    ("Cochera Central", TipoCentro.COCHERA, "Polígono Inventado, nave 1"),
    ("Base Sur y taller", TipoCentro.TALLER, "Calle Ficticia 42"),
]

# Tipos de vehículo: (nombre, unidad de capacidad, km medios por día)
TIPOS_VEHICULO = [
    ("Autobús", UnidadCapacidad.PLAZAS, 260),
    ("Microbús", UnidadCapacidad.PLAZAS, 180),
    ("Furgoneta", UnidadCapacidad.KG, 150),
    ("Camión rígido", UnidadCapacidad.KG, 300),
    ("Cisterna", UnidadCapacidad.KG, 320),
]

# Modelos inventados por tipo: (marca, modelo, capacidad, combustible)
MODELOS = {
    "Autobús": [
        ("Autocar Ibérica", "Urbano 12", 55, Combustible.DIESEL),
        ("Autocar Ibérica", "Interurbano 13", 59, Combustible.DIESEL),
        ("Movilia", "E-City 12", 50, Combustible.ELECTRICO),
    ],
    "Microbús": [
        ("Movilia", "Mini 8", 22, Combustible.DIESEL),
        ("Nordia", "Shuttle 7", 19, Combustible.HIBRIDO),
    ],
    "Furgoneta": [
        ("Cargotrans", "Van 35", 1200, Combustible.DIESEL),
        ("Nordia", "E-Van", 900, Combustible.ELECTRICO),
    ],
    "Camión rígido": [
        ("Cargotrans", "R 18", 9000, Combustible.DIESEL),
        ("Pesados del Norte", "PN 26", 14000, Combustible.GNL),
    ],
    "Cisterna": [("Pesados del Norte", "Cisterna 40", 24000, Combustible.DIESEL)],
}

# Cuántos vehículos de cada tipo (en total, 25: lo que pide GEN-04).
REPARTO = {"Autobús": 9, "Microbús": 4, "Furgoneta": 5, "Camión rígido": 4, "Cisterna": 3}

# Tipos de vencimiento: (nombre, días de aviso, bloquea la salida)
TIPOS_VENC_VEHICULO = [
    ("ITV", 30, True),
    ("Seguro", 30, True),
    ("Tacógrafo", 30, True),
    ("Tarjeta de transporte", 30, True),
    ("Revisión de extintores", 15, False),  # se vigila, pero no impide salir
]
# Se crean ya para cuando lleguen las personas (PER-02).
TIPOS_VENC_PERSONA = [
    ("Permiso de conducir", 60, True),
    ("CAP", 60, True),
    ("Tarjeta de conductor", 30, True),
    ("Reconocimiento médico", 30, True),
    ("ADR", 60, True),
]
# Las furgonetas (< 3.500 kg) no llevan tacógrafo.
SIN_TACOGRAFO = {"Furgoneta"}

USUARIOS = [
    (RolUsuario.ADMIN, "admin", "Gerente (demo)"),
    (RolUsuario.TRAFICO, "trafico", "Jefa de tráfico (demo)"),
    (RolUsuario.TALLER, "taller", "Jefe de taller (demo)"),
    (RolUsuario.CONDUCTOR, "conductor", "Conductor (demo)"),
]

# Personal: (puesto, cuántos). En total, 30: lo que pide GEN-04.
REPARTO_PERSONAL = [(Puesto.CONDUCTOR, 20), (Puesto.MECANICO, 5), (Puesto.TRAFICO, 3), (Puesto.OTRO, 2)]
# Nombres y apellidos comunes, combinados al azar: personas inventadas. (Sin el nombre
# de quien firma el proyecto, para no confundir a una persona inventada con alguien real.)
NOMBRES = ["Lucía", "Hugo", "Marta", "Óscar", "Sara", "Javier", "Elena", "Daniel", "Carmen", "Álvaro",
           "Nuria", "Sergio", "Irene", "Raúl", "Paula", "Adrián", "Laura", "Diego", "Rocío", "Iván"]
APELLIDOS = ["García", "Martín", "López", "Sánchez", "Romero", "Navarro", "Torres", "Ruiz", "Gil", "Molina",
             "Ortega", "Delgado", "Castro", "Ortiz", "Rubio", "Marín", "Iglesias", "Medina", "Garrido", "Cano"]
# Documentos por puesto (nombres de TIPOS_VENC_PERSONA).
DOCUMENTOS_POR_PUESTO = {
    Puesto.CONDUCTOR: ["Permiso de conducir", "CAP", "Tarjeta de conductor", "Reconocimiento médico"],
    Puesto.MECANICO: ["Reconocimiento médico"],
}
CONDUCTORES_CON_ADR = 3  # los primeros conductores también llevan mercancías peligrosas
# Casos especiales de personal: nº de persona -> (documento, días hasta caducar)
CASOS_ESPECIALES_PERSONAL = {
    0: ("CAP", -10),  # rojo
    1: ("Tarjeta de conductor", 12),  # ámbar (aviso 30)
    2: ("Permiso de conducir", 40),  # ámbar (aviso 60)
}
# Qué persona corresponde a cada usuario demo: (rol del usuario, puesto, nº de esa persona dentro del puesto)
ENLACE_USUARIOS = {
    RolUsuario.ADMIN: (Puesto.OTRO, 0),
    RolUsuario.TRAFICO: (Puesto.TRAFICO, 0),
    RolUsuario.TALLER: (Puesto.MECANICO, 0),
    RolUsuario.CONDUCTOR: (Puesto.CONDUCTOR, 3),  # un conductor con la documentación en regla
}

# Planes preventivos por tipo: (nombre, intervalo_km, intervalo_dias, tareas)
_ACEITE = ["Cambio de aceite del motor", "Filtro de aceite", "Filtro de aire", "Filtro de combustible"]
_FRENOS = ["Pastillas y discos de freno", "Líquido de frenos", "Prueba de frenada"]
PLANES_DEMO = {
    "Autobús": [
        ("Mantenimiento A", 30_000, 365, _ACEITE),
        ("Revisión de frenos", 60_000, None, _FRENOS),
        ("Revisión anual", None, 365, ["Climatización", "Puertas y rampa", "Alumbrado", "Extintores"]),
    ],
    "Microbús": [("Mantenimiento A", 25_000, 365, _ACEITE)],
    "Furgoneta": [("Mantenimiento A", 20_000, 365, _ACEITE)],
    "Camión rígido": [("Mantenimiento A", 40_000, 365, _ACEITE), ("Revisión de frenos", 80_000, None, _FRENOS)],
    "Cisterna": [
        ("Mantenimiento A", 40_000, 365, _ACEITE),
        ("Revisión de la cisterna", None, 180, ["Estanqueidad", "Válvulas", "Toma de tierra"]),
    ],
}
# Casos especiales de preventivo: nº de vehículo -> (plan, caso)
CASOS_ESPECIALES_PREVENTIVO = {
    6: ("Mantenimiento A", "vencido_km"),
    7: ("Revisión anual", "vencido_fecha"),
    8: ("Mantenimiento A", "proximo_km"),
    9: ("Mantenimiento A", "proximo_fecha"),  # el primer microbús
}

# Averías de la demo: nº de vehículo -> (gravedad, descripción, ¿resuelta?, hace cuántos días)
AVERIAS_DEMO = [
    (10, GravedadAveria.INMOVILIZA, "No arranca: la batería no carga y salta un fallo eléctrico", False, 0),
    (11, GravedadAveria.GRAVE, "Ruido metálico en la caja de cambios al reducir de marcha", False, 1),
    (12, GravedadAveria.LEVE, "El retrovisor derecho vibra en carretera", False, 2),
    (13, GravedadAveria.LEVE, "Luz de cortesía del pasillo fundida", True, 9),
]

# Órdenes de trabajo de la demo (MAN-04 a MAN-06). Precios inventados pero verosímiles.
TARIFA_HORA = Decimal("45.00")
# Recambios de cada plan preventivo: (descripción, cantidad, precio mínimo, precio máximo)
RECAMBIOS_PLAN = {
    "Mantenimiento A": [("Aceite de motor (litros)", 30, "3.10", "4.20"), ("Filtro de aceite", 1, "14", "26"),
                        ("Filtro de aire", 1, "22", "48"), ("Filtro de combustible", 1, "18", "39")],
    "Revisión de frenos": [("Juego de pastillas", 2, "48", "95"), ("Líquido de frenos (litros)", 2, "9", "14")],
    "Revisión anual": [("Kit de revisión de climatización", 1, "35", "60")],
    "Revisión de la cisterna": [("Juntas y precintos de válvulas", 1, "40", "90")],
}
EXTERNO_PLAN = {"Revisión de la cisterna": ("Prueba de estanqueidad (taller homologado)", "220", "320")}
# Correctivas típicas: (descripción, horas mín, horas máx, recambios [(descripción, precio mín, precio máx)])
CORRECTIVAS_DEMO = [
    ("Sustitución de pastillas y discos delanteros", 2, 4, [("Discos de freno", "180", "260"), ("Pastillas", "60", "110")]),
    ("Fuga en el circuito de refrigeración", 1, 3, [("Manguito de refrigeración", "25", "60"), ("Anticongelante", "20", "35")]),
    ("Alternador sin carga", 2, 3, [("Alternador reconstruido", "240", "420")]),
    ("Avería en la puerta de servicio", 1, 2, [("Electroválvula de puerta", "90", "160")]),
    ("Pinchazo y cambio de neumático", 1, 1, [("Neumático", "210", "340")]),
    ("Luces de posición traseras fundidas", 0.5, 1, [("Grupo óptico trasero", "45", "95")]),
    ("Ruido en la suspensión trasera", 2, 5, [("Amortiguador", "120", "210")]),
    ("Fallo del aire acondicionado", 2, 4, [("Recarga de gas y compresor", "180", "390")]),
    ("Batería descargada", 0.5, 1, [("Batería 12 V", "130", "220")]),
    ("Sensor de temperatura defectuoso", 1, 2, [("Sensor de temperatura", "35", "70")]),
]
# Catálogo de recambios (MAN-09): (referencia, nombre, precio de catálogo). Los nombres coinciden
# con los recambios de las OT de la demo, que quedan enlazados al catálogo. El precio de cada OT
# varía alrededor del de catálogo (como en la realidad: cambian proveedor, ofertas…).
CATALOGO_DEMO = [
    ("ACE-1040-L", "Aceite de motor (litros)", "3.65"),
    ("FIL-ACE-210", "Filtro de aceite", "20.00"),
    ("FIL-AIR-330", "Filtro de aire", "35.00"),
    ("FIL-COM-115", "Filtro de combustible", "28.50"),
    ("FRE-PAS-JG4", "Juego de pastillas", "71.50"),
    ("FRE-LIQ-DOT4", "Líquido de frenos (litros)", "11.50"),
    ("CLI-KIT-REV", "Kit de revisión de climatización", "47.50"),
    ("CIS-JUN-VAL", "Juntas y precintos de válvulas", "65.00"),
    ("FRE-DIS-DEL", "Discos de freno", "220.00"),
    ("FRE-PAS-DEL", "Pastillas", "85.00"),
    ("REF-MAN-50", "Manguito de refrigeración", "42.50"),
    ("REF-ANT-5L", "Anticongelante", "27.50"),
    ("ELE-ALT-RCN", "Alternador reconstruido", "330.00"),
    ("CAR-EVP-PS", "Electroválvula de puerta", "125.00"),
    ("NEU-315-80", "Neumático", "275.00"),
    ("ILU-GOT-TR", "Grupo óptico trasero", "70.00"),
    ("SUS-AMO-TR", "Amortiguador", "165.00"),
    ("CLI-COMP-GAS", "Recarga de gas y compresor", "285.00"),
    ("ELE-BAT-12V", "Batería 12 V", "175.00"),
    ("MOT-SEN-TMP", "Sensor de temperatura", "52.50"),
    ("TRA-EMB-KIT", "Kit de embrague", "485.00"),
]

# Abiertas en este momento: nº de vehículo -> (descripción, ¿en curso?, ¿inmoviliza?)
OT_EN_CURSO_DEMO = (14, "Sustitución del kit de embrague", True)

# Casos especiales para que el panel tenga de todo: nº de vehículo -> (documento, días hasta caducar)
CASOS_ESPECIALES = {
    0: ("ITV", -12),  # rojo: NO apto
    1: ("Seguro", -3),  # rojo: NO apto
    2: ("ITV", 5),  # ámbar
    3: ("Tacógrafo", 18),  # ámbar
    4: ("Seguro", 27),  # ámbar
    5: ("Revisión de extintores", -20),  # rojo, pero no bloquea: sigue siendo apto
}

_CONSONANTES = "BCDFGHJKLMNPRSTVWXYZ"  # las matrículas españolas no usan vocales


# --- 1. Planificar (Python puro) ---------------------------------------------


@dataclass
class VehiculoPlan:
    matricula: str
    tipo: str
    marca: str
    modelo: str
    anio: int
    capacidad: int
    combustible: Combustible
    centro: int  # índice en CENTROS
    lecturas: list[tuple[date, int]] = field(default_factory=list)
    vencimientos: list[tuple[str, date]] = field(default_factory=list)


def planificar_demo(hoy: date, semilla: int = SEMILLA) -> list[VehiculoPlan]:
    """Genera los 25 vehículos con sus lecturas de km y vencimientos (siempre los mismos)."""
    rng = random.Random(semilla)
    km_por_dia = {nombre: km for nombre, _, km in TIPOS_VEHICULO}
    inicio = hoy - timedelta(days=DIAS_DE_HISTORIAL)
    matriculas: set[str] = set()
    plan: list[VehiculoPlan] = []

    for tipo, cantidad in REPARTO.items():
        for _ in range(cantidad):
            # Matrícula única con formato 0000XXX.
            while True:
                matricula = f"{rng.randint(0, 9999):04d}" + "".join(rng.choices(_CONSONANTES, k=3))
                if matricula not in matriculas:
                    matriculas.add(matricula)
                    break
            marca, modelo, capacidad, combustible = rng.choice(MODELOS[tipo])
            v = VehiculoPlan(
                matricula=matricula,
                tipo=tipo,
                marca=marca,
                modelo=modelo,
                anio=rng.randint(2012, hoy.year - 1),
                capacidad=capacidad,
                combustible=combustible,
                centro=len(plan) % len(CENTROS),
            )

            # Lecturas de km semanales durante ~6 meses, siempre crecientes.
            # Km iniciales coherentes con la antigüedad: días en servicio hasta el inicio
            # del historial x km diarios de su tipo (con algo de variación).
            dias_en_servicio = max((inicio - date(v.anio, 7, 1)).days, 30)
            km = int(dias_en_servicio * km_por_dia[tipo] * rng.uniform(0.6, 1.0))
            fecha = inicio
            while fecha <= hoy:
                v.lecturas.append((fecha, km))
                km += int(km_por_dia[tipo] * 7 * rng.uniform(0.6, 1.2))
                fecha += timedelta(days=7)

            # Vencimientos vigentes: en verde, salvo los casos especiales.
            especial = CASOS_ESPECIALES.get(len(plan))
            for nombre, _, _ in TIPOS_VENC_VEHICULO:
                if nombre == "Tacógrafo" and tipo in SIN_TACOGRAFO:
                    continue
                dias = especial[1] if especial and especial[0] == nombre else rng.randint(45, 360)
                caduca = hoy + timedelta(days=dias)
                v.vencimientos.append((nombre, caduca))
                if nombre == "ITV":
                    # La ITV anterior, ya renovada: queda como historial.
                    v.vencimientos.append((nombre, caduca - timedelta(days=365)))

            plan.append(v)
    return plan


@dataclass
class PersonaPlan:
    nombre: str
    puesto: Puesto
    centro: int  # índice en CENTROS
    fecha_alta: date
    vencimientos: list[tuple[str, date]] = field(default_factory=list)


def planificar_personal(hoy: date, semilla: int = SEMILLA) -> list[PersonaPlan]:
    """Genera las 30 personas con su documentación (siempre las mismas)."""
    rng = random.Random(semilla + 1)  # semilla propia: no altera los vehículos
    nombres: set[str] = set()
    plan: list[PersonaPlan] = []
    conductores = 0
    for puesto, cantidad in REPARTO_PERSONAL:
        for _ in range(cantidad):
            while True:
                nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
                if nombre not in nombres:
                    nombres.add(nombre)
                    break
            p = PersonaPlan(
                nombre=nombre,
                puesto=puesto,
                centro=len(plan) % len(CENTROS),
                fecha_alta=hoy - timedelta(days=rng.randint(60, 3650)),
            )
            documentos = list(DOCUMENTOS_POR_PUESTO.get(puesto, []))
            if puesto == Puesto.CONDUCTOR:
                if conductores < CONDUCTORES_CON_ADR:
                    documentos.append("ADR")
                conductores += 1
            especial = CASOS_ESPECIALES_PERSONAL.get(len(plan))
            for doc in documentos:
                # Verde: más allá del mayor plazo de aviso (60 días), salvo los casos especiales.
                dias = especial[1] if especial and especial[0] == doc else rng.randint(70, 1500)
                p.vencimientos.append((doc, hoy + timedelta(days=dias)))
            plan.append(p)
    return plan


@dataclass(frozen=True)
class AsignacionPlan:
    persona: int  # índice en el plan de personal (los conductores son los primeros)
    vehiculo: int  # índice en el plan de vehículos
    desde: date
    hasta: date | None
    habitual: bool


def planificar_asignaciones(hoy: date, personal: list[PersonaPlan], semilla: int = SEMILLA) -> list[AsignacionPlan]:
    """Cada conductor es el habitual de un vehículo; 5 vehículos con un habitual anterior
    ya terminado (historial) y 2 asignaciones temporales (una pasada y una futura).

    Respeta PER-03: ningún vehículo tiene dos habituales solapados.
    """
    rng = random.Random(semilla + 2)
    conductores = [i for i, p in enumerate(personal) if p.puesto == Puesto.CONDUCTOR]
    plan: list[AsignacionPlan] = []
    for n, persona in enumerate(conductores):  # conductor n -> vehículo n
        desde = max(personal[persona].fecha_alta, hoy - timedelta(days=rng.randint(30, 300)))
        plan.append(AsignacionPlan(persona, n, desde, None, True))
        if n < 5:  # historial: el habitual anterior de este vehículo, ya terminado
            anterior = conductores[(n + 10) % len(conductores)]
            hasta_anterior = desde - timedelta(days=1)
            desde_anterior = hasta_anterior - timedelta(days=rng.randint(90, 300))
            plan.append(AsignacionPlan(anterior, n, desde_anterior, hasta_anterior, True))
    # Temporales: una sustitución pasada y un refuerzo la semana que viene.
    plan.append(AsignacionPlan(conductores[15], 21, hoy - timedelta(days=40), hoy - timedelta(days=33), False))
    plan.append(AsignacionPlan(conductores[16], 22, hoy + timedelta(days=7), hoy + timedelta(days=11), False))
    return plan


@dataclass(frozen=True)
class PreventivoPlan:
    vehiculo: int  # índice en el plan de vehículos
    plan: str  # nombre del plan (dentro de su tipo)
    ultima_fecha: date
    ultimos_km: int


def planificar_preventivos(hoy: date, vehiculos: list[VehiculoPlan], semilla: int = SEMILLA) -> list[PreventivoPlan]:
    """Último mantenimiento de cada plan en cada vehículo: casi todos al día, salvo los casos especiales.

    Los normales se hicieron hace como mucho un 80 % del intervalo (fuera del margen de previsión).
    """
    rng = random.Random(semilla + 3)
    km_por_dia = {nombre: km for nombre, _, km in TIPOS_VEHICULO}
    resultado: list[PreventivoPlan] = []
    for n, v in enumerate(vehiculos):
        km_actuales = v.lecturas[-1][1]
        for nombre, intervalo_km, intervalo_dias, _ in PLANES_DEMO[v.tipo]:
            especial = CASOS_ESPECIALES_PREVENTIVO.get(n)
            caso = especial[1] if especial and especial[0] == nombre else None
            if caso == "vencido_km":
                dias_desde, km_desde = 90, intervalo_km + 1_500
            elif caso == "vencido_fecha":
                dias_desde, km_desde = intervalo_dias + 15, 5_000
            elif caso == "proximo_km":
                dias_desde, km_desde = 60, intervalo_km - 1_200
            elif caso == "proximo_fecha":
                dias_desde, km_desde = intervalo_dias - 12, 5_000
            else:
                dias_desde = rng.randint(10, int((intervalo_dias or 250) * 0.8))
                km_desde = int(dias_desde * km_por_dia[v.tipo] * rng.uniform(0.6, 0.9))
                if intervalo_km:
                    km_desde = min(km_desde, int(intervalo_km * 0.8))
            resultado.append(
                PreventivoPlan(n, nombre, hoy - timedelta(days=dias_desde), max(km_actuales - km_desde, 0))
            )
    return resultado


@dataclass
class OTPlan:
    vehiculo: int
    tipo: TipoOT
    origen: OrigenOT
    descripcion: str
    abierta: date
    cerrada: date | None  # None: sigue abierta o en curso
    km: int | None
    inmoviliza: bool
    lineas: list[tuple[Concepto, str, Decimal, Decimal]]  # (concepto, descripción, cantidad, precio)
    plan: str | None = None  # nombre del plan (preventivas)
    en_curso: bool = False


def _precio(rng: random.Random, minimo: str, maximo: str) -> Decimal:
    return Decimal(str(round(rng.uniform(float(minimo), float(maximo)), 2)))


def _horas(rng: random.Random, minimo: float, maximo: float) -> Decimal:
    return Decimal(str(round(rng.uniform(minimo, maximo) * 2) / 2))  # de media en media hora


def planificar_ordenes(
    hoy: date, vehiculos: list[VehiculoPlan], preventivos: list[PreventivoPlan], semilla: int = SEMILLA
) -> list[OTPlan]:
    """6 meses de historial: preventivas (una por cada preventivo realizado en ese plazo),
    10 correctivas cerradas y, abierta ahora, una en curso que inmoviliza."""
    rng = random.Random(semilla + 4)
    inicio = hoy - timedelta(days=DIAS_DE_HISTORIAL)
    plan: list[OTPlan] = []

    for prev in preventivos:
        if prev.ultima_fecha < inicio:
            continue
        lineas = [(Concepto.MANO_OBRA, "Mano de obra del taller", _horas(rng, 1, 4), TARIFA_HORA)]
        for desc, cantidad, minimo, maximo in RECAMBIOS_PLAN[prev.plan]:
            lineas.append((Concepto.RECAMBIO, desc, Decimal(cantidad), _precio(rng, minimo, maximo)))
        if prev.plan in EXTERNO_PLAN:
            desc, minimo, maximo = EXTERNO_PLAN[prev.plan]
            lineas.append((Concepto.EXTERNO, desc, Decimal(1), _precio(rng, minimo, maximo)))
        plan.append(OTPlan(prev.vehiculo, TipoOT.PREVENTIVA, OrigenOT.PLAN, prev.plan,
                           prev.ultima_fecha - timedelta(days=1), prev.ultima_fecha, prev.ultimos_km, True, lineas, prev.plan))

    for desc, h_min, h_max, recambios in CORRECTIVAS_DEMO:
        n = rng.randrange(len(vehiculos))
        cerrada = inicio + timedelta(days=rng.randint(5, DIAS_DE_HISTORIAL - 5))
        # Km de cierre: los de la última lectura de ese vehículo hasta esa fecha (coherentes con FLO-05).
        km = max(k for f, k in vehiculos[n].lecturas if f <= cerrada)
        lineas = [(Concepto.MANO_OBRA, "Mano de obra del taller", _horas(rng, h_min, h_max), TARIFA_HORA)]
        lineas += [(Concepto.RECAMBIO, d, Decimal(1), _precio(rng, mn, mx)) for d, mn, mx in recambios]
        plan.append(OTPlan(n, TipoOT.CORRECTIVA, OrigenOT.MANUAL, desc, cerrada - timedelta(days=rng.randint(0, 2)),
                           cerrada, km, rng.random() < 0.5, lineas))

    n, desc, inmoviliza = OT_EN_CURSO_DEMO
    plan.append(OTPlan(n, TipoOT.CORRECTIVA, OrigenOT.MANUAL, desc, hoy - timedelta(days=1), None, None, inmoviliza,
                       [(Concepto.MANO_OBRA, "Desmontaje de la caja de cambios", Decimal("3.5"), TARIFA_HORA),
                        (Concepto.RECAMBIO, "Kit de embrague", Decimal(1), Decimal("485.00"))], en_curso=True))
    return plan


# --- 2. Guardar en la base de datos ------------------------------------------


@dataclass
class ResumenDemo:
    empresa_id: int
    centros: int
    vehiculos: int
    lecturas_km: int
    vencimientos: int
    no_aptos: list[str]  # matrículas de los vehículos que no pueden salir
    en_ambar: list[str]  # matrículas con algún documento a punto de caducar
    usuarios: list[str]  # emails para hacer login
    personas: int = 0
    asignaciones: int = 0
    asignaciones_con_aviso: list[str] = field(default_factory=list)  # "persona → matrícula" con aviso PER-04
    planes: int = 0
    preventivos_vencidos: list[str] = field(default_factory=list)  # "matrícula: plan (motivo)"
    preventivos_proximos: list[str] = field(default_factory=list)
    ordenes: int = 0
    recambios: int = 0  # en el catálogo
    ordenes_abiertas: list[str] = field(default_factory=list)  # "matrícula: descripción (estado)"
    coste_mantenimiento: Decimal = Decimal("0.00")  # suma de las OT cerradas
    personas_en_rojo: list[str] = field(default_factory=list)  # nombres con documentación caducada
    personas_en_ambar: list[str] = field(default_factory=list)  # nombres con documentación a punto de caducar


class DemoYaExiste(Exception):
    """Ya hay una empresa demo; usar reiniciar=True para recrearla."""


def email_demo(alias: str) -> str:
    return f"{alias}@{DOMINIO}"


def buscar_empresa_demo(db: Session) -> int | None:
    """Id de la empresa demo (la del usuario admin@demo.example.com), o None."""
    return db.scalar(select(Usuario.empresa_id).where(Usuario.email == email_demo("admin")))


def borrar_empresa(db: Session, empresa_id: int) -> None:
    """Borra una empresa y TODOS sus datos, en orden (de las tablas hijas a la empresa).

    Incluidos los archivos de las fotos de sus averías: si no, quedarían huérfanos en disco.
    """
    for foto in db.scalars(select(Averia.foto).where(Averia.empresa_id == empresa_id, Averia.foto.is_not(None))):
        borrar_foto(foto)
    # Asignacion y Vencimiento antes que Vehiculo y Persona; Persona antes que Usuario (lo referencia).
    for modelo in (
        LineaOT, Recambio, OrdenTrabajo, Averia, Asignacion, Vencimiento, EstadoPlan, LecturaKm, Vehiculo, Persona,
        TareaPlan, PlanMantenimiento, TipoVencimiento, TipoVehiculo, Centro, Usuario,
    ):
        db.execute(delete(modelo).where(modelo.empresa_id == empresa_id))
    db.execute(delete(Empresa).where(Empresa.id == empresa_id))


def crear_empresa_demo(
    db: Session, hoy: date | None = None, password: str = PASSWORD_DEMO, reiniciar: bool = False
) -> ResumenDemo:
    """Crea la empresa demo completa (sin commit: lo hace quien llama).

    Si ya existe: con reiniciar=True se borra y se vuelve a crear; si no, DemoYaExiste.
    Nunca toca otras empresas.
    """
    hoy = hoy or date.today()
    existente = buscar_empresa_demo(db)
    if existente is not None:
        if not reiniciar:
            raise DemoYaExiste("Ya existe la empresa demo (usa --reiniciar para recrearla)")
        borrar_empresa(db, existente)
        db.flush()

    empresa = Empresa(nombre=NOMBRE_EMPRESA)
    db.add(empresa)
    db.flush()
    eid = empresa.id

    centros = [Centro(empresa_id=eid, nombre=n, tipo=t, direccion=d) for n, t, d in CENTROS]
    tipos_vehiculo = {n: TipoVehiculo(empresa_id=eid, nombre=n, unidad_capacidad=u) for n, u, _ in TIPOS_VEHICULO}
    tipos_venc = {
        n: TipoVencimiento(empresa_id=eid, nombre=n, dias_aviso=d, bloquea_salida=b, aplica_a=AplicaA.VEHICULO)
        for n, d, b in TIPOS_VENC_VEHICULO
    }
    tipos_persona = {
        n: TipoVencimiento(empresa_id=eid, nombre=n, dias_aviso=d, bloquea_salida=b, aplica_a=AplicaA.PERSONA)
        for n, d, b in TIPOS_VENC_PERSONA
    }
    hash_demo = hash_password(password)  # un solo hash para todos: Argon2 es lento a propósito
    usuarios = [
        Usuario(empresa_id=eid, email=email_demo(alias), nombre=nombre, hash_password=hash_demo, rol=rol)
        for rol, alias, nombre in USUARIOS
    ]
    db.add_all([*centros, *tipos_vehiculo.values(), *tipos_venc.values(), *tipos_persona.values(), *usuarios])
    db.flush()

    no_aptos: list[str] = []
    en_ambar: list[str] = []
    n_lecturas = n_vencimientos = 0
    vehiculos_creados: list[Vehiculo] = []
    docs_por_vehiculo: dict[int, list[Documento]] = {}
    for p in planificar_demo(hoy):
        vehiculo = Vehiculo(
            empresa_id=eid,
            centro_id=centros[p.centro].id,
            tipo_id=tipos_vehiculo[p.tipo].id,
            matricula=p.matricula,
            marca=p.marca,
            modelo=p.modelo,
            anio=p.anio,
            capacidad=p.capacidad,
            combustible=p.combustible,
            km_actuales=p.lecturas[-1][1],  # FLO-05: los de la última lectura
        )
        db.add(vehiculo)
        db.flush()
        vehiculos_creados.append(vehiculo)
        db.add_all(LecturaKm(empresa_id=eid, vehiculo_id=vehiculo.id, fecha=f, km=k) for f, k in p.lecturas)
        db.add_all(
            Vencimiento(empresa_id=eid, vehiculo_id=vehiculo.id, tipo_id=tipos_venc[n].id, fecha_caducidad=f)
            for n, f in p.vencimientos
        )
        actualizar_estado(db, vehiculo)  # regla 1: el estado lo decide el motor
        n_lecturas += len(p.lecturas)
        n_vencimientos += len(p.vencimientos)

        # Documentos para el resumen (se calcula al final, cuando ya hay averías).
        docs_por_vehiculo[vehiculo.id] = [
            Documento(tipos_venc[n].id, n, f, tipos_venc[n].dias_aviso, tipos_venc[n].bloquea_salida)
            for n, f in p.vencimientos
        ]

    # Personal (PER-01) con su documentación (PER-02).
    usuario_por_rol = {u.rol: u for u in usuarios}
    # (puesto, nº dentro del puesto) -> rol del usuario que le corresponde.
    rol_de_persona = {clave: rol for rol, clave in ENLACE_USUARIOS.items()}
    personas_en_rojo: list[str] = []
    personas_en_ambar: list[str] = []
    plan_personal = planificar_personal(hoy)
    vistos_por_puesto: dict[Puesto, int] = {}
    personas_creadas: list[Persona] = []
    documentos_persona: list[list[Documento]] = []
    for pp in plan_personal:
        n_en_puesto = vistos_por_puesto.get(pp.puesto, 0)
        vistos_por_puesto[pp.puesto] = n_en_puesto + 1
        rol = rol_de_persona.get((pp.puesto, n_en_puesto))
        usuario_enlazado = usuario_por_rol[rol] if rol else None
        persona = Persona(
            empresa_id=eid,
            nombre=pp.nombre,
            puesto=pp.puesto,
            centro_id=centros[pp.centro].id,
            fecha_alta=pp.fecha_alta,
            usuario_id=usuario_enlazado.id if usuario_enlazado else None,
        )
        db.add(persona)
        db.flush()
        personas_creadas.append(persona)
        documentos_persona.append(
            [Documento(tipos_persona[n].id, n, f, tipos_persona[n].dias_aviso, tipos_persona[n].bloquea_salida) for n, f in pp.vencimientos]
        )
        db.add_all(
            Vencimiento(empresa_id=eid, persona_id=persona.id, tipo_id=tipos_persona[n].id, fecha_caducidad=f)
            for n, f in pp.vencimientos
        )
        n_vencimientos += len(pp.vencimientos)
        colores = {semaforo(f, tipos_persona[n].dias_aviso, hoy) for n, f in pp.vencimientos}
        if Semaforo.ROJO in colores:
            personas_en_rojo.append(pp.nombre)
        elif Semaforo.AMBAR in colores:
            personas_en_ambar.append(pp.nombre)

    # Asignaciones conductor-vehículo con historial (PER-03) y avisos (PER-04).
    plan_asignaciones = planificar_asignaciones(hoy, plan_personal)
    asignaciones_con_aviso: list[str] = []
    for pa in plan_asignaciones:
        persona, vehiculo = personas_creadas[pa.persona], vehiculos_creados[pa.vehiculo]
        db.add(
            Asignacion(
                empresa_id=eid, persona_id=persona.id, vehiculo_id=vehiculo.id,
                desde=pa.desde, hasta=pa.hasta, habitual=pa.habitual,
            )
        )
        en_vigor_o_futura = pa.hasta is None or pa.hasta >= hoy
        if en_vigor_o_futura and avisos_de_documentacion(documentos_persona[pa.persona], max(pa.desde, hoy)):
            asignaciones_con_aviso.append(f"{persona.nombre} → {vehiculo.matricula}")

    # Planes preventivos (MAN-01) y su estado en cada vehículo.
    planes: dict[tuple[str, str], PlanMantenimiento] = {}
    for tipo, lista in PLANES_DEMO.items():
        for nombre, intervalo_km, intervalo_dias, tareas in lista:
            plan_m = PlanMantenimiento(
                empresa_id=eid, tipo_vehiculo_id=tipos_vehiculo[tipo].id, nombre=nombre,
                intervalo_km=intervalo_km, intervalo_dias=intervalo_dias,
            )
            db.add(plan_m)
            db.flush()
            db.add_all(TareaPlan(empresa_id=eid, plan_id=plan_m.id, orden=i, descripcion=t) for i, t in enumerate(tareas, 1))
            planes[(tipo, nombre)] = plan_m
    plan_vehiculos = planificar_demo(hoy)
    preventivos_vencidos: list[str] = []
    preventivos_proximos: list[str] = []
    for prev in planificar_preventivos(hoy, plan_vehiculos):
        vehiculo = vehiculos_creados[prev.vehiculo]
        plan_m = planes[(plan_vehiculos[prev.vehiculo].tipo, prev.plan)]
        estado = EstadoPlan(
            empresa_id=eid, vehiculo_id=vehiculo.id, plan_id=plan_m.id,
            ultima_fecha=prev.ultima_fecha, ultimos_km=prev.ultimos_km,
        )
        recalcular(estado, plan_m)
        db.add(estado)
        e = evaluar(
            calcular_proximo(prev.ultima_fecha, prev.ultimos_km, plan_m.intervalo_dias, plan_m.intervalo_km),
            hoy, vehiculo.km_actuales,
        )
        if e.situacion == Situacion.VENCIDO:
            preventivos_vencidos.append(f"{vehiculo.matricula}: {prev.plan} ({e.motivo})")
        elif e.situacion == Situacion.PROXIMO:
            preventivos_proximos.append(f"{vehiculo.matricula}: {prev.plan} ({e.motivo})")

    # Averías (MAN-03), comunicadas por el conductor demo. El estado lo recalcula el motor.
    conductor_demo = next(u for u in usuarios if u.rol == RolUsuario.CONDUCTOR)
    for n, gravedad, descripcion, resuelta, hace in AVERIAS_DEMO:
        vehiculo = vehiculos_creados[n]
        cuando = datetime.combine(hoy - timedelta(days=hace), time(9, 30), tzinfo=UTC)
        db.add(
            Averia(
                empresa_id=eid, vehiculo_id=vehiculo.id, comunicada_por_id=conductor_demo.id,
                comunicada_en=cuando, descripcion=descripcion, gravedad=gravedad,
                estado=EstadoAveria.RESUELTA if resuelta else EstadoAveria.COMUNICADA,
                resuelta_en=cuando + timedelta(days=1) if resuelta else None,
                nota_resolucion="Sustituida" if resuelta else None,
            )
        )
        db.flush()
        actualizar_estado(db, vehiculo)

    # Catálogo de recambios (MAN-09), antes de las OT para enlazar sus líneas.
    catalogo = [Recambio(empresa_id=eid, referencia=r, nombre=n, precio=Decimal(p)) for r, n, p in CATALOGO_DEMO]
    db.add_all(catalogo)
    db.flush()
    recambio_por_nombre = {r.nombre: r.id for r in catalogo}

    # Órdenes de trabajo (MAN-04 a MAN-06): 6 meses de historial y las abiertas ahora.
    taller_demo = next(u for u in usuarios if u.rol == RolUsuario.TALLER)
    plan_ordenes = planificar_ordenes(hoy, plan_vehiculos, planificar_preventivos(hoy, plan_vehiculos))
    ordenes_abiertas: list[str] = []
    coste_mantenimiento = Decimal("0.00")
    for o in plan_ordenes:
        vehiculo = vehiculos_creados[o.vehiculo]
        ot = OrdenTrabajo(
            empresa_id=eid, vehiculo_id=vehiculo.id, tipo=o.tipo, origen=o.origen, descripcion=o.descripcion,
            plan_id=planes[(plan_vehiculos[o.vehiculo].tipo, o.plan)].id if o.plan else None,
            inmoviliza=o.inmoviliza, creada_por_id=taller_demo.id,
            abierta_en=datetime.combine(o.abierta, time(8, 0), tzinfo=UTC),
            estado=EstadoOT.EN_CURSO if o.en_curso else EstadoOT.CERRADA,
            iniciada_en=datetime.combine(o.abierta, time(9, 0), tzinfo=UTC),
            fecha_cierre=o.cerrada, km_cierre=o.km,
        )
        db.add(ot)
        db.flush()
        db.add_all(LineaOT(empresa_id=eid, ot_id=ot.id, concepto=c, descripcion=d, cantidad=q, precio_unitario=pr,
                           recambio_id=recambio_por_nombre.get(d) if c == Concepto.RECAMBIO else None)
                   for c, d, q, pr in o.lineas)
        if o.cerrada:
            coste_mantenimiento += coste(Linea(c, q, pr) for c, _, q, pr in o.lineas).total
        else:
            ordenes_abiertas.append(f"{vehiculo.matricula}: {o.descripcion} (en curso)")

    # La avería grave abierta pasa a una OT (MAN-04: queda "en reparación").
    grave = db.scalar(select(Averia).where(Averia.empresa_id == eid, Averia.gravedad == GravedadAveria.GRAVE))
    if grave is not None:
        db.add(OrdenTrabajo(
            empresa_id=eid, vehiculo_id=grave.vehiculo_id, tipo=TipoOT.CORRECTIVA, origen=OrigenOT.AVERIA,
            averia_id=grave.id, inmoviliza=False, descripcion=grave.descripcion, creada_por_id=taller_demo.id,
        ))
        grave.estado = EstadoAveria.EN_REPARACION
        ordenes_abiertas.append(f"{next(v.matricula for v in vehiculos_creados if v.id == grave.vehiculo_id)}: {grave.descripcion} (abierta)")
    db.flush()
    for vehiculo in vehiculos_creados:
        actualizar_estado(db, vehiculo)

    # Resumen con las mismas reglas que usa la API (ya con el estado final de cada vehículo).
    for vehiculo in vehiculos_creados:
        docs = docs_por_vehiculo[vehiculo.id]
        if not aptitud_para_salir(True, vehiculo.estado, docs, hoy).apto:
            no_aptos.append(vehiculo.matricula)
        if any(semaforo(d.fecha_caducidad, d.dias_aviso, hoy) == Semaforo.AMBAR for d in vigentes(docs)):
            en_ambar.append(vehiculo.matricula)

    db.flush()
    return ResumenDemo(
        empresa_id=eid,
        centros=len(centros),
        vehiculos=sum(REPARTO.values()),
        lecturas_km=n_lecturas,
        vencimientos=n_vencimientos,
        no_aptos=no_aptos,
        en_ambar=en_ambar,
        usuarios=[u.email for u in usuarios],
        personas=len(plan_personal),
        personas_en_rojo=personas_en_rojo,
        personas_en_ambar=personas_en_ambar,
        asignaciones=len(plan_asignaciones),
        asignaciones_con_aviso=asignaciones_con_aviso,
        planes=len(planes),
        preventivos_vencidos=preventivos_vencidos,
        preventivos_proximos=preventivos_proximos,
        ordenes=len(plan_ordenes) + (1 if grave is not None else 0),
        recambios=len(catalogo),
        ordenes_abiertas=ordenes_abiertas,
        coste_mantenimiento=coste_mantenimiento,
    )
