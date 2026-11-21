"""lecturas de km

Tabla lectura_km (FLO-05) y, para los vehículos que ya existían, una lectura
inicial con sus km actuales (migración de datos).

Revisado a mano: la restricción única de vehiculo se crea ANTES que la tabla,
porque la FK compuesta de lectura_km la necesita (autogenerate la ponía después).

Revision ID: c8b8963af6d6
Revises: 157b9ac88ced
Create Date: 2026-11-21 20:32:49.111211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b8963af6d6'
down_revision: Union[str, Sequence[str], None] = '157b9ac88ced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Primero la restricción única: la FK compuesta de lectura_km apunta a ella.
    op.create_unique_constraint(op.f('uq_vehiculo_empresa_id_id'), 'vehiculo', ['empresa_id', 'id'])

    # 2. La tabla de lecturas.
    op.create_table('lectura_km',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vehiculo_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('km', sa.Integer(), nullable=False),
    sa.Column('registrada_por_id', sa.Integer(), nullable=True),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('km >= 0 AND km <= 10000000', name=op.f('ck_lectura_km_km_razonables')),
    sa.ForeignKeyConstraint(['empresa_id', 'vehiculo_id'], ['vehiculo.empresa_id', 'vehiculo.id'], name='fk_lectura_km_vehiculo_misma_empresa', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_lectura_km_empresa_id_empresa'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['registrada_por_id'], ['usuario.id'], name=op.f('fk_lectura_km_registrada_por_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lectura_km'))
    )
    op.create_index(op.f('ix_lectura_km_empresa_id'), 'lectura_km', ['empresa_id'], unique=False)
    op.create_index('ix_lectura_km_vehiculo_id_fecha', 'lectura_km', ['vehiculo_id', 'fecha'], unique=False)

    # 3. Migración de datos: cada vehículo existente recibe una lectura inicial
    #    con sus km actuales, fechada el día en que se dio de alta.
    op.execute(
        """
        INSERT INTO lectura_km (empresa_id, vehiculo_id, fecha, km)
        SELECT empresa_id, id, creado_en::date, km_actuales
        FROM vehiculo
        """
    )


def downgrade() -> None:
    """Downgrade schema (orden inverso: primero la tabla, después la restricción)."""
    op.drop_index('ix_lectura_km_vehiculo_id_fecha', table_name='lectura_km')
    op.drop_index(op.f('ix_lectura_km_empresa_id'), table_name='lectura_km')
    op.drop_table('lectura_km')
    op.drop_constraint(op.f('uq_vehiculo_empresa_id_id'), 'vehiculo', type_='unique')
