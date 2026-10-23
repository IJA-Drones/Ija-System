"""vigilância: execuções da migração de dados legados (TR 4.7)

Revision ID: f90ef50fbda0
Revises: 4956d97d273e
"""
from alembic import op
import sqlalchemy as sa

revision = "f90ef50fbda0"
down_revision = "4956d97d273e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vigilancia_migracoes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("prefeitura", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("destino", sa.String(20), nullable=False),
        sa.Column("fonte", sa.String(120), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("formato", sa.String(10), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original", sa.LargeBinary(), nullable=False),
        sa.Column("extraido", sa.LargeBinary(), nullable=False),
        sa.Column("adequado", sa.LargeBinary(), nullable=True),
        sa.Column("etapa", sa.String(20), nullable=False),
        sa.Column("extracao", sa.JSON(), nullable=False),
        sa.Column("mapeamento", sa.JSON(), nullable=True),
        sa.Column("relatorio", sa.JSON(), nullable=True),
        sa.Column("resultado", sa.JSON(), nullable=True),
        sa.Column("criado", sa.Float(), nullable=False),
        sa.Column("atualizado", sa.Float(), nullable=False),
        sa.CheckConstraint("destino IN ('visitas','sinan','quarteiroes')", name="ck_migracao_destino"),
        sa.CheckConstraint("etapa IN ('EXTRAIDO','VALIDADO','CONCLUIDO')", name="ck_migracao_etapa"),
    )
    op.create_index("ix_migracao_prefeitura_data", "vigilancia_migracoes", ["prefeitura", "criado"])


def downgrade():
    op.drop_index("ix_migracao_prefeitura_data", table_name="vigilancia_migracoes")
    op.drop_table("vigilancia_migracoes")
