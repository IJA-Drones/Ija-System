"""rastro GPS dos agentes de endemias

Revision ID: 74f7339f497d
Revises: fde67898a660
"""
from alembic import op
import sqlalchemy as sa

revision = "74f7339f497d"
down_revision = "fde67898a660"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vigilancia_agente_posicoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False, index=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=True, index=True),
        sa.Column("latitude", sa.Float(), nullable=False), sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("precisao_m", sa.Float()),
        sa.Column("registrado_em", sa.DateTime(), nullable=False, index=True),
        sa.Column("origem", sa.String(10), nullable=False, server_default="web"),
    )


def downgrade():
    op.drop_table("vigilancia_agente_posicoes")
