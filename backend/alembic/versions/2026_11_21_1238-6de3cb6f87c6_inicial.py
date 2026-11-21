"""inicial

Migración base, vacía a propósito: marca el punto de partida del historial
y comprueba que Alembic se conecta a la BD. Las tablas llegan en la siguiente.

Revision ID: 6de3cb6f87c6
Revises: 
Create Date: 2026-11-21 12:38:58.060694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6de3cb6f87c6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
