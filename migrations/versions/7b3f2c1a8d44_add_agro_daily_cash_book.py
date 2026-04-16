"""add agro daily cash book

Revision ID: 7b3f2c1a8d44
Revises: fc12a9d4b7e2
Create Date: 2026-04-16 10:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "7b3f2c1a8d44"
down_revision = "fc12a9d4b7e2"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade():
    bind = op.get_bind()
    if _table_exists(bind, "financeiro_agro_caixa_diario"):
        return

    op.create_table(
        "financeiro_agro_caixa_diario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("data_caixa", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ABERTO"),
        sa.Column("saldo_anterior", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("saldo_abertura", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_entradas", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_saidas", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("saldo_fechamento", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("aberto_por_nome", sa.String(length=120), nullable=True),
        sa.Column("fechado_por_nome", sa.String(length=120), nullable=True),
        sa.Column("observacoes_abertura", sa.Text(), nullable=True),
        sa.Column("observacoes_fechamento", sa.Text(), nullable=True),
        sa.Column("aberto_em", sa.DateTime(), nullable=False),
        sa.Column("fechado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefeitura_id", "data_caixa", name="uq_financeiro_agro_caixa_diario_prefeitura_data"),
    )

    op.create_index(op.f("ix_financeiro_agro_caixa_diario_id"), "financeiro_agro_caixa_diario", ["id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_prefeitura_id"), "financeiro_agro_caixa_diario", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_data_caixa"), "financeiro_agro_caixa_diario", ["data_caixa"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_status"), "financeiro_agro_caixa_diario", ["status"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_aberto_em"), "financeiro_agro_caixa_diario", ["aberto_em"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_fechado_em"), "financeiro_agro_caixa_diario", ["fechado_em"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_criado_em"), "financeiro_agro_caixa_diario", ["criado_em"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_caixa_diario_atualizado_em"), "financeiro_agro_caixa_diario", ["atualizado_em"], unique=False)
    op.create_index("ix_financeiro_agro_caixa_diario_status_data", "financeiro_agro_caixa_diario", ["status", "data_caixa"], unique=False)


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "financeiro_agro_caixa_diario"):
        return

    op.drop_index("ix_financeiro_agro_caixa_diario_status_data", table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_atualizado_em"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_criado_em"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_fechado_em"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_aberto_em"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_status"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_data_caixa"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_prefeitura_id"), table_name="financeiro_agro_caixa_diario")
    op.drop_index(op.f("ix_financeiro_agro_caixa_diario_id"), table_name="financeiro_agro_caixa_diario")
    op.drop_table("financeiro_agro_caixa_diario")
