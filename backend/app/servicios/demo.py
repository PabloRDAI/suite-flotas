"""Empresa de demostración con datos ficticios (GEN-04).

Dos piezas:
- planificar_demo(): Python puro. Decide QUÉ datos crear, con una semilla fija:
  cada ejecución genera exactamente los mismos datos (reproducible y testeable).
- crear_empresa_demo(): guarda el plan en la base de datos.

Todo es inventado: nombre de empresa, marcas, matrículas y emails
(@demo.example.com, dominio reservado para ejemplos). Las fechas son relativas a
"hoy", así que siempre hay vencimientos en rojo y en ámbar para enseñar.

Pendiente de ampliar cuando existan sus tablas: 30 personas (fase de personal)
y 6 meses de historial de mantenimiento (fase de mantenimiento).
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    AplicaA,
    Centro,
    Combustible,
    Empresa,
    LecturaKm,
    RolUsuario,
    TipoCentro,
    TipoVehiculo,
    TipoVencimiento,
    UnidadCapacidad,
    Usuario,
    Vehiculo,
    Vencimiento,
)
from app.reglas.vencimientos import Documento, Semaforo, aptitud_para_salir, semaforo, vigentes
from app.seguridad import hash_password
from app.servicios.estado_vehiculo import actualizar_estado

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
                anio=rng.randint(2012, hoy.year),
                capacidad=capacidad,
                combustible=combustible,
                centro=len(plan) % len(CENTROS),
            )

            # Lecturas de km semanales durante ~6 meses, siempre crecientes.
            km = rng.randint(15_000, 450_000)
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


class DemoYaExiste(Exception):
    """Ya hay una empresa demo; usar reiniciar=True para recrearla."""


def email_demo(alias: str) -> str:
    return f"{alias}@{DOMINIO}"


def buscar_empresa_demo(db: Session) -> int | None:
    """Id de la empresa demo (la del usuario admin@demo.example.com), o None."""
    return db.scalar(select(Usuario.empresa_id).where(Usuario.email == email_demo("admin")))


def borrar_empresa(db: Session, empresa_id: int) -> None:
    """Borra una empresa y TODOS sus datos, en orden (de las tablas hijas a la empresa)."""
    for modelo in (Vencimiento, LecturaKm, Vehiculo, TipoVencimiento, TipoVehiculo, Centro, Usuario):
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
    tipos_persona = [
        TipoVencimiento(empresa_id=eid, nombre=n, dias_aviso=d, bloquea_salida=b, aplica_a=AplicaA.PERSONA)
        for n, d, b in TIPOS_VENC_PERSONA
    ]
    hash_demo = hash_password(password)  # un solo hash para todos: Argon2 es lento a propósito
    usuarios = [
        Usuario(empresa_id=eid, email=email_demo(alias), nombre=nombre, hash_password=hash_demo, rol=rol)
        for rol, alias, nombre in USUARIOS
    ]
    db.add_all([*centros, *tipos_vehiculo.values(), *tipos_venc.values(), *tipos_persona, *usuarios])
    db.flush()

    no_aptos: list[str] = []
    en_ambar: list[str] = []
    n_lecturas = n_vencimientos = 0
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
        db.add_all(LecturaKm(empresa_id=eid, vehiculo_id=vehiculo.id, fecha=f, km=k) for f, k in p.lecturas)
        db.add_all(
            Vencimiento(empresa_id=eid, vehiculo_id=vehiculo.id, tipo_id=tipos_venc[n].id, fecha_caducidad=f)
            for n, f in p.vencimientos
        )
        actualizar_estado(db, vehiculo)  # regla 1: el estado lo decide el motor
        n_lecturas += len(p.lecturas)
        n_vencimientos += len(p.vencimientos)

        # Resumen con las mismas reglas que usa la API.
        docs = [
            Documento(tipos_venc[n].id, n, f, tipos_venc[n].dias_aviso, tipos_venc[n].bloquea_salida)
            for n, f in p.vencimientos
        ]
        if not aptitud_para_salir(True, vehiculo.estado, docs, hoy).apto:
            no_aptos.append(p.matricula)
        if any(semaforo(d.fecha_caducidad, d.dias_aviso, hoy) == Semaforo.AMBAR for d in vigentes(docs)):
            en_ambar.append(p.matricula)

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
    )
