"""add financeiro agro table

Revision ID: e7a1c4f9b2d3
Revises: d9a7c3b1f2e4, f2a3b4c5d6e7
Create Date: 2026-04-13 13:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e7a1c4f9b2d3"
down_revision = ("d9a7c3b1f2e4", "f2a3b4c5d6e7")
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade():
    bind = op.get_bind()
    if _table_exists(bind, "financeiro_agro"):
        return

    op.create_table(
        "financeiro_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("cliente_agro_id", sa.Integer(), nullable=True),
        sa.Column("orcamento_agro_id", sa.Integer(), nullable=True),
        sa.Column("contrato_agro_id", sa.Integer(), nullable=False),
        sa.Column("ordem_servico_agro_id", sa.Integer(), nullable=True),
        sa.Column("cliente_nome", sa.String(length=150), nullable=False),
        sa.Column("cultura", sa.String(length=100), nullable=True),
        sa.Column("forma_recebimento", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDENTE"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("competencia_mes", sa.Integer(), nullable=True),
        sa.Column("competencia_ano", sa.Integer(), nullable=True),
        sa.Column("data_elaboracao_contrato", sa.Date(), nullable=True),
        sa.Column("data_servico_executado", sa.Date(), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=False),
        sa.Column("data_recebimento", sa.Date(), nullable=True),
        sa.Column("area_mapeamento_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("valor_mapeamento_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_mapeamento", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("area_pulverizacao_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("area_pulverizada_real_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("valor_pulverizacao_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_pulverizacao", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("valor_total_contrato", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("comissao_por_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="8"),
        sa.Column("valor_comissao", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("comissao_cooperativa_por_ha", sa.Numeric(precision=12, scale=2), nullable=False, server_default="10"),
        sa.Column("valor_comissao_cooperativa", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cliente_agro_id"], ["clientes_agro.id"]),
        sa.ForeignKeyConstraint(["contrato_agro_id"], ["contratos_agro.id"]),
        sa.ForeignKeyConstraint(["orcamento_agro_id"], ["orcamentos_agro.id"]),
        sa.ForeignKeyConstraint(["ordem_servico_agro_id"], ["ordens_servico_agro.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_financeiro_agro_id"), "financeiro_agro", ["id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_prefeitura_id"), "financeiro_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_cliente_agro_id"), "financeiro_agro", ["cliente_agro_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_orcamento_agro_id"), "financeiro_agro", ["orcamento_agro_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_contrato_agro_id"), "financeiro_agro", ["contrato_agro_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_ordem_servico_agro_id"), "financeiro_agro", ["ordem_servico_agro_id"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_cliente_nome"), "financeiro_agro", ["cliente_nome"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_cultura"), "financeiro_agro", ["cultura"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_status"), "financeiro_agro", ["status"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_competencia_mes"), "financeiro_agro", ["competencia_mes"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_competencia_ano"), "financeiro_agro", ["competencia_ano"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_data_elaboracao_contrato"), "financeiro_agro", ["data_elaboracao_contrato"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_data_servico_executado"), "financeiro_agro", ["data_servico_executado"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_data_vencimento"), "financeiro_agro", ["data_vencimento"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_data_recebimento"), "financeiro_agro", ["data_recebimento"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_criado_em"), "financeiro_agro", ["criado_em"], unique=False)
    op.create_index(op.f("ix_financeiro_agro_atualizado_em"), "financeiro_agro", ["atualizado_em"], unique=False)
    op.create_index("ix_financeiro_agro_status_vencimento", "financeiro_agro", ["status", "data_vencimento"], unique=False)
    op.create_index("ix_financeiro_agro_competencia", "financeiro_agro", ["competencia_ano", "competencia_mes"], unique=False)
    op.create_index("ix_financeiro_agro_contrato_vencimento", "financeiro_agro", ["contrato_agro_id", "data_vencimento"], unique=False)


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "financeiro_agro"):
        return

    op.drop_index("ix_financeiro_agro_contrato_vencimento", table_name="financeiro_agro")
    op.drop_index("ix_financeiro_agro_competencia", table_name="financeiro_agro")
    op.drop_index("ix_financeiro_agro_status_vencimento", table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_atualizado_em"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_criado_em"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_data_recebimento"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_data_vencimento"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_data_servico_executado"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_data_elaboracao_contrato"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_competencia_ano"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_competencia_mes"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_status"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_cultura"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_cliente_nome"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_ordem_servico_agro_id"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_contrato_agro_id"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_orcamento_agro_id"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_cliente_agro_id"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_prefeitura_id"), table_name="financeiro_agro")
    op.drop_index(op.f("ix_financeiro_agro_id"), table_name="financeiro_agro")
    op.drop_table("financeiro_agro")
