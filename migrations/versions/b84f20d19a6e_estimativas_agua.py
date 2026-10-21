"""Estimativas de água localizadas no levantamento."""
from alembic import op
import sqlalchemy as sa

revision = 'b84f20d19a6e'
down_revision = 'a73e5c9b204f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ortomosaico_estimativas_agua',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ortomosaico_id', sa.Integer(), sa.ForeignKey('ortomosaicos.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('dados', sa.JSON(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_ortomosaico_estimativas_agua_ortomosaico_id',
                    'ortomosaico_estimativas_agua', ['ortomosaico_id'])


def downgrade():
    op.drop_table('ortomosaico_estimativas_agua')
