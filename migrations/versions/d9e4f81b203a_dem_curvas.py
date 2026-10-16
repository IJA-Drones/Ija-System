"""DEM contour outputs alongside existing orthomosaics; preserves RGB records."""
from alembic import op
import sqlalchemy as sa

revision = 'd9e4f81b203a'
down_revision = 'c8d3e70a192f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ortomosaicos', sa.Column('tipo', sa.String(20), nullable=False, server_default='rgb'))
    op.add_column('ortomosaicos', sa.Column('intervalo_m', sa.Float()))
    op.add_column('ortomosaicos', sa.Column('resolucao_m', sa.Float()))
    op.add_column('ortomosaicos', sa.Column('curvas_path', sa.String(512)))
    op.add_column('ortomosaicos', sa.Column('jpeg_path', sa.String(512)))


def downgrade():
    for name in ('jpeg_path', 'curvas_path', 'resolucao_m', 'intervalo_m', 'tipo'):
        op.drop_column('ortomosaicos', name)
