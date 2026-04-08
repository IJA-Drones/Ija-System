"""add agro management tables

Revision ID: e3b7a9c4d2f1
Revises: d91f4a7c2b10
Create Date: 2026-04-08 15:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3b7a9c4d2f1"
down_revision = "d91f4a7c2b10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clientes_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("documento", sa.String(length=50), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cep", sa.String(length=9), nullable=False),
        sa.Column("logradouro", sa.String(length=150), nullable=False),
        sa.Column("numero", sa.String(length=20), nullable=False),
        sa.Column("complemento", sa.String(length=100), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=False),
        sa.Column("cidade", sa.String(length=100), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("documento"),
    )
    op.create_index(op.f("ix_clientes_agro_id"), "clientes_agro", ["id"], unique=False)
    op.create_index(op.f("ix_clientes_agro_prefeitura_id"), "clientes_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_clientes_agro_documento"), "clientes_agro", ["documento"], unique=False)
    op.create_index(op.f("ix_clientes_agro_nome"), "clientes_agro", ["nome"], unique=False)
    op.create_index(op.f("ix_clientes_agro_bairro"), "clientes_agro", ["bairro"], unique=False)
    op.create_index(op.f("ix_clientes_agro_cidade"), "clientes_agro", ["cidade"], unique=False)
    op.create_index(op.f("ix_clientes_agro_uf"), "clientes_agro", ["uf"], unique=False)
    op.create_index(op.f("ix_clientes_agro_criado_em"), "clientes_agro", ["criado_em"], unique=False)

    op.create_table(
        "equipes_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_equipes_agro_id"), "equipes_agro", ["id"], unique=False)
    op.create_index(op.f("ix_equipes_agro_prefeitura_id"), "equipes_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_equipes_agro_nome"), "equipes_agro", ["nome"], unique=False)
    op.create_index(op.f("ix_equipes_agro_ativa"), "equipes_agro", ["ativa"], unique=False)
    op.create_index(op.f("ix_equipes_agro_criado_em"), "equipes_agro", ["criado_em"], unique=False)

    op.create_table(
        "pilotos_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("equipe_agro_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["equipe_agro_id"], ["equipes_agro.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pilotos_agro_id"), "pilotos_agro", ["id"], unique=False)
    op.create_index(op.f("ix_pilotos_agro_prefeitura_id"), "pilotos_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_pilotos_agro_equipe_agro_id"), "pilotos_agro", ["equipe_agro_id"], unique=False)
    op.create_index(op.f("ix_pilotos_agro_nome"), "pilotos_agro", ["nome"], unique=False)
    op.create_index(op.f("ix_pilotos_agro_ativo"), "pilotos_agro", ["ativo"], unique=False)
    op.create_index(op.f("ix_pilotos_agro_criado_em"), "pilotos_agro", ["criado_em"], unique=False)

    op.create_table(
        "equipamentos_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("equipe_agro_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("identificacao", sa.String(length=100), nullable=False),
        sa.Column("numero_serie", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["equipe_agro_id"], ["equipes_agro.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_serie"),
    )
    op.create_index(op.f("ix_equipamentos_agro_id"), "equipamentos_agro", ["id"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_prefeitura_id"), "equipamentos_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_equipe_agro_id"), "equipamentos_agro", ["equipe_agro_id"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_tipo"), "equipamentos_agro", ["tipo"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_modelo"), "equipamentos_agro", ["modelo"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_identificacao"), "equipamentos_agro", ["identificacao"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_numero_serie"), "equipamentos_agro", ["numero_serie"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_status"), "equipamentos_agro", ["status"], unique=False)
    op.create_index(op.f("ix_equipamentos_agro_criado_em"), "equipamentos_agro", ["criado_em"], unique=False)

    op.create_table(
        "orcamentos_agro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefeitura_id", sa.Integer(), nullable=True),
        sa.Column("cliente_agro_id", sa.Integer(), nullable=False),
        sa.Column("cliente_nome", sa.String(length=150), nullable=False),
        sa.Column("nome_fazenda", sa.String(length=150), nullable=False),
        sa.Column("mapeamento", sa.Boolean(), nullable=False),
        sa.Column("risco_operacional", sa.Text(), nullable=True),
        sa.Column("cultura", sa.String(length=100), nullable=True),
        sa.Column("cep", sa.String(length=9), nullable=False),
        sa.Column("logradouro", sa.String(length=150), nullable=False),
        sa.Column("numero", sa.String(length=20), nullable=False),
        sa.Column("complemento", sa.String(length=100), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=False),
        sa.Column("cidade", sa.String(length=100), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("anexo_path", sa.String(length=255), nullable=True),
        sa.Column("anexo_nome", sa.String(length=255), nullable=True),
        sa.Column("protocolo", sa.String(length=80), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cliente_agro_id"], ["clientes_agro.id"]),
        sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orcamentos_agro_id"), "orcamentos_agro", ["id"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_prefeitura_id"), "orcamentos_agro", ["prefeitura_id"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_cliente_agro_id"), "orcamentos_agro", ["cliente_agro_id"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_cliente_nome"), "orcamentos_agro", ["cliente_nome"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_nome_fazenda"), "orcamentos_agro", ["nome_fazenda"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_mapeamento"), "orcamentos_agro", ["mapeamento"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_cultura"), "orcamentos_agro", ["cultura"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_bairro"), "orcamentos_agro", ["bairro"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_cidade"), "orcamentos_agro", ["cidade"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_uf"), "orcamentos_agro", ["uf"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_protocolo"), "orcamentos_agro", ["protocolo"], unique=False)
    op.create_index(op.f("ix_orcamentos_agro_data_criacao"), "orcamentos_agro", ["data_criacao"], unique=False)
    op.create_index("ix_orcamentos_agro_cliente_data", "orcamentos_agro", ["cliente_agro_id", "data_criacao"], unique=False)
    op.create_index("ix_orcamentos_agro_protocolo_data", "orcamentos_agro", ["protocolo", "data_criacao"], unique=False)


def downgrade():
    op.drop_index("ix_orcamentos_agro_protocolo_data", table_name="orcamentos_agro")
    op.drop_index("ix_orcamentos_agro_cliente_data", table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_data_criacao"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_protocolo"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_uf"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_cidade"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_bairro"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_cultura"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_mapeamento"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_nome_fazenda"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_cliente_nome"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_cliente_agro_id"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_prefeitura_id"), table_name="orcamentos_agro")
    op.drop_index(op.f("ix_orcamentos_agro_id"), table_name="orcamentos_agro")
    op.drop_table("orcamentos_agro")

    op.drop_index(op.f("ix_equipamentos_agro_criado_em"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_status"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_numero_serie"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_identificacao"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_modelo"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_tipo"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_equipe_agro_id"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_prefeitura_id"), table_name="equipamentos_agro")
    op.drop_index(op.f("ix_equipamentos_agro_id"), table_name="equipamentos_agro")
    op.drop_table("equipamentos_agro")

    op.drop_index(op.f("ix_pilotos_agro_criado_em"), table_name="pilotos_agro")
    op.drop_index(op.f("ix_pilotos_agro_ativo"), table_name="pilotos_agro")
    op.drop_index(op.f("ix_pilotos_agro_nome"), table_name="pilotos_agro")
    op.drop_index(op.f("ix_pilotos_agro_equipe_agro_id"), table_name="pilotos_agro")
    op.drop_index(op.f("ix_pilotos_agro_prefeitura_id"), table_name="pilotos_agro")
    op.drop_index(op.f("ix_pilotos_agro_id"), table_name="pilotos_agro")
    op.drop_table("pilotos_agro")

    op.drop_index(op.f("ix_equipes_agro_criado_em"), table_name="equipes_agro")
    op.drop_index(op.f("ix_equipes_agro_ativa"), table_name="equipes_agro")
    op.drop_index(op.f("ix_equipes_agro_nome"), table_name="equipes_agro")
    op.drop_index(op.f("ix_equipes_agro_prefeitura_id"), table_name="equipes_agro")
    op.drop_index(op.f("ix_equipes_agro_id"), table_name="equipes_agro")
    op.drop_table("equipes_agro")

    op.drop_index(op.f("ix_clientes_agro_criado_em"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_uf"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_cidade"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_bairro"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_nome"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_documento"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_prefeitura_id"), table_name="clientes_agro")
    op.drop_index(op.f("ix_clientes_agro_id"), table_name="clientes_agro")
    op.drop_table("clientes_agro")
