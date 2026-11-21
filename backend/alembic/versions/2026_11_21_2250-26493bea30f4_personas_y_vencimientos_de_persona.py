"""personas y vencimientos de persona

Revision ID: 26493bea30f4
Revises: 4be3aa75ab03
Create Date: 2026-11-21 22:50:28.644953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26493bea30f4'
down_revision: Union[str, Sequence[str], None] = '4be3aa75ab03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Revisado a mano:
    - uq_usuario_empresa_id_id se crea ANTES que persona (su FK compuesta la necesita).
    - El CHECK un_solo_titular de vencimiento se añade a mano: autogenerate no
      detecta restricciones CHECK nuevas en tablas que ya existen.
    """
    op.create_unique_constraint(op.f('uq_usuario_empresa_id_id'), 'usuario', ['empresa_id', 'id'])

    op.create_table('persona',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('puesto', sa.Enum('conductor', 'mecanico', 'trafico', 'otro', name='puesto', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('centro_id', sa.Integer(), nullable=False),
    sa.Column('fecha_alta', sa.Date(), nullable=False),
    sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('fecha_baja', sa.Date(), nullable=True),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['empresa_id', 'centro_id'], ['centro.empresa_id', 'centro.id'], name='fk_persona_centro_misma_empresa'),
    sa.ForeignKeyConstraint(['empresa_id', 'usuario_id'], ['usuario.empresa_id', 'usuario.id'], name='fk_persona_usuario_misma_empresa'),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_persona_empresa_id_empresa'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_persona')),
    sa.UniqueConstraint('empresa_id', 'id', name=op.f('uq_persona_empresa_id_id')),
    sa.UniqueConstraint('usuario_id', name=op.f('uq_persona_usuario_id'))
    )
    op.create_index(op.f('ix_persona_centro_id'), 'persona', ['centro_id'], unique=False)
    op.create_index(op.f('ix_persona_empresa_id'), 'persona', ['empresa_id'], unique=False)

    # Vencimientos: ahora el titular puede ser un vehículo o una persona.
    op.add_column('vencimiento', sa.Column('persona_id', sa.Integer(), nullable=True))
    op.alter_column('vencimiento', 'vehiculo_id', existing_type=sa.INTEGER(), nullable=True)
    op.create_index('ix_vencimiento_persona_id_tipo_id', 'vencimiento', ['persona_id', 'tipo_id'], unique=False)
    op.create_foreign_key(
        'fk_vencimiento_persona_misma_empresa', 'vencimiento', 'persona',
        ['empresa_id', 'persona_id'], ['empresa_id', 'id'], ondelete='CASCADE',
    )
    # Exactamente un titular. Los vencimientos existentes son todos de vehículo: lo cumplen.
    op.create_check_constraint(
        op.f('ck_vencimiento_un_solo_titular'), 'vencimiento', 'num_nonnulls(vehiculo_id, persona_id) = 1'
    )


def downgrade() -> None:
    """Downgrade schema (orden inverso al de upgrade).

    ATENCIÓN: borra los vencimientos de persona, que no caben en el esquema anterior.
    """
    op.drop_constraint(op.f('ck_vencimiento_un_solo_titular'), 'vencimiento', type_='check')
    op.drop_constraint('fk_vencimiento_persona_misma_empresa', 'vencimiento', type_='foreignkey')
    op.drop_index('ix_vencimiento_persona_id_tipo_id', table_name='vencimiento')
    op.execute("DELETE FROM vencimiento WHERE persona_id IS NOT NULL")
    op.alter_column('vencimiento', 'vehiculo_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_column('vencimiento', 'persona_id')

    op.drop_index(op.f('ix_persona_empresa_id'), table_name='persona')
    op.drop_index(op.f('ix_persona_centro_id'), table_name='persona')
    op.drop_table('persona')
    # Después de la tabla persona, que dependía de ella.
    op.drop_constraint(op.f('uq_usuario_empresa_id_id'), 'usuario', type_='unique')
