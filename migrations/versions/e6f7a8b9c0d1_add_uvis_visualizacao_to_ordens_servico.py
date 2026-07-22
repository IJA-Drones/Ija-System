"""add uvis visualizacao to ordens servico

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.add_column(sa.Column("uvis_visualizado", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("uvis_visualizado_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("uvis_visualizado_por_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ordens_servico_uvis_visualizado_por_id_usuarios",
            "usuarios",
            ["uvis_visualizado_por_id"],
            ["id"],
        )
        batch_op.create_index("ix_ordens_servico_uvis_visualizado", ["uvis_visualizado"], unique=False)
        batch_op.create_index("ix_ordens_servico_uvis_visualizado_em", ["uvis_visualizado_em"], unique=False)
        batch_op.create_index("ix_ordens_servico_uvis_visualizado_por_id", ["uvis_visualizado_por_id"], unique=False)


def downgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.drop_index("ix_ordens_servico_uvis_visualizado_por_id")
        batch_op.drop_index("ix_ordens_servico_uvis_visualizado_em")
        batch_op.drop_index("ix_ordens_servico_uvis_visualizado")
        batch_op.drop_constraint("fk_ordens_servico_uvis_visualizado_por_id_usuarios", type_="foreignkey")
        batch_op.drop_column("uvis_visualizado_por_id")
        batch_op.drop_column("uvis_visualizado_em")
        batch_op.drop_column("uvis_visualizado")
