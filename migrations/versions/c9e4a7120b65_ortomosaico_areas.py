"""Áreas medidas e recortes visuais do ortomosaico."""
from alembic import op
import sqlalchemy as sa

revision = 'c9e4a7120b65'
down_revision = 'b7d3e9f102a4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ortomosaico_areas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ortomosaico_id', sa.Integer(), sa.ForeignKey('ortomosaicos.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL')),
        sa.Column('dados', sa.JSON(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_ortomosaico_areas_ortomosaico_id',
                    'ortomosaico_areas', ['ortomosaico_id'])


def downgrade():
    op.drop_table('ortomosaico_areas')
