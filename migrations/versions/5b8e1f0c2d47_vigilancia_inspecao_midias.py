"""fotos e vídeos das inspeções de campo (imóveis pendentes)

Revision ID: 5b8e1f0c2d47
Revises: a880745899f8
"""
from alembic import op
import sqlalchemy as sa

revision = "5b8e1f0c2d47"
down_revision = "a880745899f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vigilancia_inspecao_midias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefeitura", sa.Integer(), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("inspecao_code", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("arquivo_path", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("autor", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura", "demo", "origin", "inspecao_code"],
                                ["vigilancia_campo_inspecoes.prefeitura", "vigilancia_campo_inspecoes.demo",
                                 "vigilancia_campo_inspecoes.origin", "vigilancia_campo_inspecoes.code"],
                                name="fk_inspecao_midia_inspecao", ondelete="CASCADE"),
        sa.CheckConstraint("tipo IN ('foto','video')", name="ck_inspecao_midia_tipo"),
    )
    op.create_index("ix_inspecao_midia_inspecao", "vigilancia_inspecao_midias", ["prefeitura", "demo", "origin", "inspecao_code"])


def downgrade():
    op.drop_index("ix_inspecao_midia_inspecao", table_name="vigilancia_inspecao_midias")
    op.drop_table("vigilancia_inspecao_midias")
