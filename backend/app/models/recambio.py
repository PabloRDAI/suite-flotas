"""Catálogo de recambios (MAN-09): referencia y precio, SIN control de stock.

El precio del catálogo es el precio POR DEFECTO: al añadir el recambio a una OT se copia
a la línea, que se puede ajustar. Cambiar después el precio del catálogo no altera las
OT ya registradas (su coste es el que fue).
"""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.comun import ConMarcasDeTiempo, DeEmpresa


class Recambio(DeEmpresa, ConMarcasDeTiempo, Base):
    __tablename__ = "recambio"
    __table_args__ = (
        UniqueConstraint("empresa_id", "referencia"),  # la referencia no se repite en la empresa
        UniqueConstraint("empresa_id", "id"),  # para la FK compuesta desde las líneas de OT
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    referencia: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(150))
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Baja lógica: un recambio que ya no se usa sigue enlazado a las OT antiguas.
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())

    def __repr__(self) -> str:
        return f"<Recambio {self.id} {self.referencia!r}>"
