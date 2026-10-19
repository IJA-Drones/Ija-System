"""Snapshots agregados do mapa de risco, sem alterar dados operacionais.

Revision ID: f2a6d9c1074e
Revises: e91c7b4a203d
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a6d9c1074e"
down_revision = "e91c7b4a203d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vigilancia_risco_analises",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("prefeitura", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("fonte", sa.String(200), nullable=False),
        sa.Column("criado", sa.Float(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.UniqueConstraint("prefeitura", "demo", "digest", name="uq_risco_analise_snapshot"))
    op.create_index("ix_risco_analise_prefeitura_demo", "vigilancia_risco_analises", ["prefeitura", "demo"])


def downgrade():
    op.drop_index("ix_risco_analise_prefeitura_demo", table_name="vigilancia_risco_analises")
    op.drop_table("vigilancia_risco_analises")
