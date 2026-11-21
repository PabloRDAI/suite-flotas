"""Usuario que entra en la aplicación, con su rol (login y permisos: GEN-02)."""

from enum import StrEnum

from sqlalchemy import String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa, enum_texto


class RolUsuario(StrEnum):
    ADMIN = "admin"  # gerente: configura la empresa y consulta costes
    TRAFICO = "trafico"  # jefe de tráfico: flota, asignaciones, vencimientos
    TALLER = "taller"  # jefe de taller o mecánico: averías y órdenes de trabajo
    CONDUCTOR = "conductor"  # comunica averías


class Usuario(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("empresa_id", "id"),)  # para la FK compuesta desde persona

    id: Mapped[int] = mapped_column(primary_key=True)
    # El email identifica al usuario al hacer login: único en toda la aplicación.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    # Nunca se guarda la contraseña, solo su hash (argon2 o bcrypt).
    hash_password: Mapped[str] = mapped_column(String(255))
    rol: Mapped[RolUsuario] = mapped_column(enum_texto(RolUsuario, "rol_usuario"))
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.email!r} {self.rol}>"
