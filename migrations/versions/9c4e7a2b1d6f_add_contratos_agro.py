"""add contratos agro

Revision ID: 9c4e7a2b1d6f
Revises: a1b2c3d4e5f6
Create Date: 2026-04-09 11:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "9c4e7a2b1d6f"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contratos_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("orcamento_agro_id", sa.Integer(), nullable=False),
        sa.Column("contratante_nome", sa.String(length=150), nullable=False),
        sa.Column("contratante_documento", sa.String(length=50), nullable=False),
        sa.Column("contratante_rg", sa.String(length=40), nullable=True),
        sa.Column("contratante_cep", sa.String(length=9), nullable=False),
        sa.Column("contratante_logradouro", sa.String(length=150), nullable=False),
        sa.Column("contratante_numero", sa.String(length=20), nullable=False),
        sa.Column("contratante_complemento", sa.String(length=100), nullable=True),
        sa.Column("contratante_bairro", sa.String(length=100), nullable=False),
        sa.Column("contratante_cidade", sa.String(length=100), nullable=False),
        sa.Column("contratante_uf", sa.String(length=2), nullable=False),
        sa.Column("propriedade_nome", sa.String(length=150), nullable=False),
        sa.Column("propriedade_cep", sa.String(length=9), nullable=False),
        sa.Column("propriedade_logradouro", sa.String(length=150), nullable=False),
        sa.Column("propriedade_numero", sa.String(length=20), nullable=False),
        sa.Column("propriedade_complemento", sa.String(length=100), nullable=True),
        sa.Column("propriedade_bairro", sa.String(length=100), nullable=False),
        sa.Column("propriedade_cidade", sa.String(length=100), nullable=False),
        sa.Column("propriedade_uf", sa.String(length=2), nullable=False),
        sa.Column("descricao_servico", sa.Text(), nullable=False),
        sa.Column("cultura", sa.String(length=100), nullable=True),
        sa.Column("area_contratada", sa.String(length=50), nullable=True),
        sa.Column("valor_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("valor_mapeamento_ha", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("valor_pulverizacao_ha", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("prazo_inicio_dias", sa.Integer(), nullable=False),
        sa.Column("prazo_pagamento_dias", sa.Integer(), nullable=False),
        sa.Column("cidade_assinatura", sa.String(length=100), nullable=False),
        sa.Column("foro_cidade", sa.String(length=100), nullable=False),
        sa.Column("data_assinatura", sa.Date(), nullable=True),
        sa.Column("observacoes_adicionais", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["orcamento_agro_id"], ["orcamentos_agro.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orcamento_agro_id"),
    )
    op.create_index(op.f("ix_contratos_agro_id"), "contratos_agro", ["id"], unique=False)
    op.create_index(op.f("ix_contratos_agro_prefeitura_id"), "contratos_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_contratos_agro_orcamento_agro_id"), "contratos_agro", ["orcamento_agro_id"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_nome"), "contratos_agro", ["contratante_nome"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_documento"), "contratos_agro", ["contratante_documento"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_rg"), "contratos_agro", ["contratante_rg"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_bairro"), "contratos_agro", ["contratante_bairro"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_cidade"), "contratos_agro", ["contratante_cidade"], unique=False)
    op.create_index(op.f("ix_contratos_agro_contratante_uf"), "contratos_agro", ["contratante_uf"], unique=False)
    op.create_index(op.f("ix_contratos_agro_propriedade_nome"), "contratos_agro", ["propriedade_nome"], unique=False)
    op.create_index(op.f("ix_contratos_agro_propriedade_bairro"), "contratos_agro", ["propriedade_bairro"], unique=False)
    op.create_index(op.f("ix_contratos_agro_propriedade_cidade"), "contratos_agro", ["propriedade_cidade"], unique=False)
    op.create_index(op.f("ix_contratos_agro_propriedade_uf"), "contratos_agro", ["propriedade_uf"], unique=False)
    op.create_index(op.f("ix_contratos_agro_cultura"), "contratos_agro", ["cultura"], unique=False)
    op.create_index(op.f("ix_contratos_agro_criado_em"), "contratos_agro", ["criado_em"], unique=False)
    op.create_index(op.f("ix_contratos_agro_atualizado_em"), "contratos_agro", ["atualizado_em"], unique=False)
    op.create_index("ix_contratos_agro_orcamento_data", "contratos_agro", ["orcamento_agro_id", "atualizado_em"], unique=False)


def downgrade():
    op.drop_index("ix_contratos_agro_orcamento_data", table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_atualizado_em"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_criado_em"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_cultura"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_propriedade_uf"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_propriedade_cidade"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_propriedade_bairro"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_propriedade_nome"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_uf"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_cidade"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_bairro"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_rg"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_documento"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_contratante_nome"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_orcamento_agro_id"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_prefeitura_id"), table_name="contratos_agro")
    op.drop_index(op.f("ix_contratos_agro_id"), table_name="contratos_agro")
    op.drop_table("contratos_agro")
