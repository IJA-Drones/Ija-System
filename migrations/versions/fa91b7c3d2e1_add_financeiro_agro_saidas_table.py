"""add financeiro agro saidas table

Revision ID: fa91b7c3d2e1
Revises: f3c8b2a1d4e5
Create Date: 2026-04-15 13:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fa91b7c3d2e1"
down_revision = "f3c8b2a1d4e5"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade():
    bind = op.get_bind()
    if _table_exists(bind, "financeiro_agro_saidas"):
        return

    op.create_table(
        "financeiro_agro_saidas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("tipo_saida", sa.String(length=30), nullable=False, server_default="DESPESA"),
        sa.Column("categoria", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=180), nullable=False),
        sa.Column("favorecido", sa.String(length=150), nullable=True),
        sa.Column("forma_pagamento", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDENTE"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("competencia_mes", sa.Integer(), nullable=True),
        sa.Column("competencia_ano", sa.Integer(), nullable=True),
        sa.Column("data_lancamento", sa.Date(), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=False),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("valor", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_financeiro_agro_saidas_id"), "financeiro_agro_saidas", ["id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_prefeitura_id"), "financeiro_agro_saidas", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_tipo_saida"), "financeiro_agro_saidas", ["tipo_saida"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_categoria"), "financeiro_agro_saidas", ["categoria"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_favorecido"), "financeiro_agro_saidas", ["favorecido"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_status"), "financeiro_agro_saidas", ["status"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_competencia_mes"), "financeiro_agro_saidas", ["competencia_mes"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_competencia_ano"), "financeiro_agro_saidas", ["competencia_ano"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_data_lancamento"), "financeiro_agro_saidas", ["data_lancamento"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_data_vencimento"), "financeiro_agro_saidas", ["data_vencimento"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_data_pagamento"), "financeiro_agro_saidas", ["data_pagamento"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_criado_em"), "financeiro_agro_saidas", ["criado_em"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_saidas_atualizado_em"), "financeiro_agro_saidas", ["atualizado_em"], unique=False)
    op.create_index("ix_financeiro_agro_saidas_competencia", "financeiro_agro_saidas", ["competencia_ano", "competencia_mes"], unique=False)
    op.create_index("ix_financeiro_agro_saidas_status_vencimento", "financeiro_agro_saidas", ["status", "data_vencimento"], unique=False)
    op.create_index("ix_financeiro_agro_saidas_tipo_status", "financeiro_agro_saidas", ["tipo_saida", "status"], unique=False)


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "financeiro_agro_saidas"):
        return

    op.drop_index("ix_financeiro_agro_saidas_tipo_status", table_name="financeiro_agro_saidas")
    op.drop_index("ix_financeiro_agro_saidas_status_vencimento", table_name="financeiro_agro_saidas")
    op.drop_index("ix_financeiro_agro_saidas_competencia", table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_atualizado_em"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_criado_em"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_data_pagamento"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_data_vencimento"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_data_lancamento"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_competencia_ano"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_competencia_mes"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_status"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_favorecido"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_categoria"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_tipo_saida"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_prefeitura_id"), table_name="financeiro_agro_saidas")
    op.drop_index(op.f("ix_financeiro_agro_saidas_id"), table_name="financeiro_agro_saidas")
    op.drop_table("financeiro_agro_saidas")
