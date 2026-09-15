"""add triagem fields to denuncias

Revision ID: 4c9b2f7a6d10
Revises: 2f6b8d1c9a43
Create Date: 2026-09-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "4c9b2f7a6d10"
down_revision = "2f6b8d1c9a43"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("denuncias", sa.Column("triado_por_id", sa.Integer(), nullable=True))
    op.add_column("denuncias", sa.Column("encaminhado_em", sa.DateTime(), nullable=True))
    op.add_column("denuncias", sa.Column("arquivado_em", sa.DateTime(), nullable=True))
    op.add_column("denuncias", sa.Column("arquivado_motivo", sa.Text(), nullable=True))
    op.create_foreign_key(None, "denuncias", "usuarios", ["triado_por_id"], ["id"])
    op.create_index(op.f("ix_denuncias_triado_por_id"), "denuncias", ["triado_por_id"], unique=False)
    op.create_index(op.f("ix_denuncias_encaminhado_em"), "denuncias", ["encaminhado_em"], unique=False)
    op.create_index(op.f("ix_denuncias_arquivado_em"), "denuncias", ["arquivado_em"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_denuncias_arquivado_em"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_encaminhado_em"), table_name="denuncias")
    op.drop_index(op.f("ix_denuncias_triado_por_id"), table_name="denuncias")
    op.drop_column("denuncias", "arquivado_motivo")
    op.drop_column("denuncias", "arquivado_em")
    op.drop_column("denuncias", "encaminhado_em")
    op.drop_column("denuncias", "triado_por_id")
