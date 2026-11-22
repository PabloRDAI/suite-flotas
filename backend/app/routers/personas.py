"""Personal (PER-01) y sus vencimientos (PER-02).

- Consulta: cualquier rol. Alta, edición, baja y documentación: admin y tráfico.
- Todo filtrado por la empresa del usuario (GEN-01): de otra empresa, 404.
- Los vencimientos usan el mismo servicio y las mismas reglas que los de vehículo.
"""

import unicodedata
from datetime import date

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import Db, GestionPersonal, UsuarioActual
from app.models import AplicaA, Centro, Persona, Puesto, Usuario, Vencimiento
from app.reglas.vencimientos import Semaforo
from app.schemas import PersonaCrear, PersonaEditar, PersonaSalida, VencimientoCrear, VencimientoSalida
from app.servicios import vencimientos as servicio_vencimientos
from app.servicios.etiquetas import etiqueta
from app.servicios.excel import Columna, libro_xlsx, respuesta_xlsx

router = APIRouter(prefix="/personas", tags=["personal"])


# --- Funciones auxiliares ----------------------------------------------------


def persona_de_mi_empresa(db: Db, usuario: Usuario, persona_id: int, solo_activas: bool) -> Persona:
    """Devuelve la persona si es de la empresa del usuario; si no, 404."""
    persona = db.scalar(select(Persona).where(Persona.id == persona_id, Persona.empresa_id == usuario.empresa_id))
    if persona is None or (solo_activas and not persona.activo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Persona no encontrada")
    return persona


def _comprobar_centro(db: Db, usuario: Usuario, centro_id: int | None) -> None:
    if centro_id is not None and not db.scalar(
        select(Centro.id).where(Centro.id == centro_id, Centro.empresa_id == usuario.empresa_id, Centro.activo)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El centro indicado no existe en tu empresa")


def _comprobar_usuario_enlazable(db: Db, usuario: Usuario, usuario_id: int, persona_id: int | None = None) -> None:
    """El usuario a enlazar debe ser de la empresa (422) y no estar enlazado a otra persona (409)."""
    if not db.scalar(select(Usuario.id).where(Usuario.id == usuario_id, Usuario.empresa_id == usuario.empresa_id)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El usuario indicado no existe en tu empresa")
    otra = db.scalar(select(Persona).where(Persona.usuario_id == usuario_id, Persona.id != (persona_id or 0)))
    if otra is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ese usuario ya está enlazado a {otra.nombre}")


def _salida(persona: Persona, semaforo: Semaforo | None = None) -> PersonaSalida:
    salida = PersonaSalida.model_validate(persona)
    if semaforo is not None:
        salida.semaforo = semaforo
    return salida


# --- Personas ----------------------------------------------------------------


@router.get("")
def listar_personas(
    usuario: UsuarioActual,
    db: Db,
    centro_id: int | None = None,
    puesto: Puesto | None = None,
    incluir_bajas: bool = False,
) -> list[PersonaSalida]:
    """Personal de la empresa con el semáforo de su documentación (2 consultas en total)."""
    consulta = select(Persona).where(Persona.empresa_id == usuario.empresa_id)
    if not incluir_bajas:
        consulta = consulta.where(Persona.activo)
    if centro_id is not None:
        consulta = consulta.where(Persona.centro_id == centro_id)
    if puesto is not None:
        consulta = consulta.where(Persona.puesto == puesto)
    personas = list(db.scalars(consulta.order_by(Persona.nombre)))

    hoy = date.today()
    documentos = servicio_vencimientos.documentos_en_bloque(
        db, usuario.empresa_id, AplicaA.PERSONA, (p.id for p in personas)
    )
    return [_salida(p, servicio_vencimientos.peor_semaforo(documentos[p.id], hoy)) for p in personas]


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


# Mismo orden que la pantalla: primero quien necesita atención (rojo, ámbar), después por nombre.
_URGENCIA = {Semaforo.ROJO: 0, Semaforo.AMBAR: 1, Semaforo.VERDE: 2}


@router.get("/exportar")
def exportar_personas(
    usuario: UsuarioActual,
    db: Db,
    centro_id: int | None = None,
    puesto: Puesto | None = None,
    incluir_bajas: bool = False,
    semaforo: Semaforo | None = None,
    buscar: str | None = None,
) -> Response:
    """GEN-06: el listado del personal en Excel, con los mismos filtros y orden que la pantalla."""
    buscado = (buscar or "").strip().lower()
    personas = sorted(
        (
            p
            for p in listar_personas(usuario, db, centro_id=centro_id, puesto=puesto, incluir_bajas=incluir_bajas)
            if (semaforo is None or p.semaforo == semaforo) and buscado in p.nombre.lower()
        ),
        key=lambda p: (_URGENCIA[p.semaforo], _sin_tildes(p.nombre)),
    )
    centros = dict(db.execute(select(Centro.id, Centro.nombre).where(Centro.empresa_id == usuario.empresa_id)).tuples().all())
    columnas = [
        Columna("Nombre", 30), Columna("Puesto", 13), Columna("Centro", 20), Columna("Fecha de alta", 13, "fecha"),
        Columna("Documentación", 20), Columna("Fecha de baja", 13, "fecha"),
    ]
    filas = [
        [p.nombre, etiqueta(p.puesto), centros.get(p.centro_id), p.fecha_alta, etiqueta(p.semaforo), p.fecha_baja]
        for p in personas
    ]
    return respuesta_xlsx(libro_xlsx("Personal", columnas, filas), "personal")


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_persona(datos: PersonaCrear, usuario: GestionPersonal, db: Db) -> PersonaSalida:
    """Alta de una persona (PER-01). Solo datos mínimos: sin DNI ni datos bancarios."""
    _comprobar_centro(db, usuario, datos.centro_id)
    if datos.usuario_id is not None:
        _comprobar_usuario_enlazable(db, usuario, datos.usuario_id)

    persona = Persona(empresa_id=usuario.empresa_id, **datos.model_dump())
    db.add(persona)
    db.commit()
    return _salida(persona)


@router.get("/{persona_id}")
def ver_persona(persona_id: int, usuario: UsuarioActual, db: Db) -> PersonaSalida:
    """Ficha de una persona (también si está de baja), con el semáforo de su documentación."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=False)
    documentos = servicio_vencimientos.documentos_en_bloque(db, usuario.empresa_id, AplicaA.PERSONA, [persona.id])
    return _salida(persona, servicio_vencimientos.peor_semaforo(documentos[persona.id], date.today()))


@router.patch("/{persona_id}")
def editar_persona(persona_id: int, datos: PersonaEditar, usuario: GestionPersonal, db: Db) -> PersonaSalida:
    """Edición parcial. Una persona de baja no se edita (404)."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=True)
    cambios = datos.model_dump(exclude_unset=True)
    _comprobar_centro(db, usuario, cambios.get("centro_id"))
    if cambios.get("usuario_id") is not None:
        _comprobar_usuario_enlazable(db, usuario, cambios["usuario_id"], persona_id=persona.id)

    for campo, valor in cambios.items():
        setattr(persona, campo, valor)
    db.commit()
    return ver_persona(persona.id, usuario, db)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja_persona(persona_id: int, usuario: GestionPersonal, db: Db) -> Response:
    """Baja lógica (PER-01): no se borra; se marca inactiva con fecha de baja y se conserva su historial."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=True)
    persona.activo = False
    persona.fecha_baja = date.today()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Vencimientos de la persona (PER-02) -------------------------------------


@router.get("/{persona_id}/vencimientos")
def listar_vencimientos(persona_id: int, usuario: UsuarioActual, db: Db) -> list[VencimientoSalida]:
    """Documentos de la persona con su semáforo (mismas reglas que FLO-06)."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=False)
    return servicio_vencimientos.listar(db, usuario.empresa_id, AplicaA.PERSONA, persona.id, date.today())


@router.post("/{persona_id}/vencimientos", status_code=status.HTTP_201_CREATED)
def registrar_vencimiento(
    persona_id: int, datos: VencimientoCrear, usuario: GestionPersonal, db: Db
) -> VencimientoSalida:
    """Registra un documento (permiso, CAP…) o su renovación. 422 si el tipo es de vehículo."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=True)
    try:
        tipo = servicio_vencimientos.tipo_para(db, usuario.empresa_id, datos.tipo_id, AplicaA.PERSONA)
    except servicio_vencimientos.TipoNoValido as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    vencimiento = Vencimiento(
        empresa_id=usuario.empresa_id,
        persona_id=persona.id,
        tipo_id=tipo.id,
        fecha_caducidad=datos.fecha_caducidad,
        notas=datos.notas,
        registrado_por_id=usuario.id,
    )
    db.add(vencimiento)
    db.commit()
    lista = servicio_vencimientos.listar(db, usuario.empresa_id, AplicaA.PERSONA, persona.id, date.today())
    return next(v for v in lista if v.id == vencimiento.id)


@router.delete("/{persona_id}/vencimientos/{vencimiento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_vencimiento(persona_id: int, vencimiento_id: int, usuario: GestionPersonal, db: Db) -> Response:
    """Borra un vencimiento registrado por error."""
    persona = persona_de_mi_empresa(db, usuario, persona_id, solo_activas=True)
    vencimiento = db.scalar(
        select(Vencimiento).where(
            Vencimiento.id == vencimiento_id,
            Vencimiento.persona_id == persona.id,
            Vencimiento.empresa_id == usuario.empresa_id,
        )
    )
    if vencimiento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vencimiento no encontrado")
    db.delete(vencimiento)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
