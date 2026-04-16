"""add agro manual entries and party address

Revision ID: fb82d1c4e6a9
Revises: fa91b7c3d2e1
Create Date: 2026-04-15 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fb82d1c4e6a9"
down_revision = "fa91b7c3d2e1"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "cliente_agro_id" not in columns:
                batch_op.add_column(sa.Column("cliente_agro_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_financeiro_agro_saidas_cliente_agro_id",
                    "clientes_agro",
                    ["cliente_agro_id"],
                    ["id"],
                )
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_cliente_agro_id"), ["cliente_agro_id"], unique=False)
            if "cep" not in columns:
                batch_op.add_column(sa.Column("cep", sa.String(length=9), nullable=True))
            if "logradouro" not in columns:
                batch_op.add_column(sa.Column("logradouro", sa.String(length=150), nullable=True))
            if "numero" not in columns:
                batch_op.add_column(sa.Column("numero", sa.String(length=20), nullable=True))
            if "complemento" not in columns:
                batch_op.add_column(sa.Column("complemento", sa.String(length=100), nullable=True))
            if "bairro" not in columns:
                batch_op.add_column(sa.Column("bairro", sa.String(length=100), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_bairro"), ["bairro"], unique=False)
            if "cidade" not in columns:
                batch_op.add_column(sa.Column("cidade", sa.String(length=100), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_cidade"), ["cidade"], unique=False)
            if "uf" not in columns:
                batch_op.add_column(sa.Column("uf", sa.String(length=2), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_uf"), ["uf"], unique=False)

    if not _table_exists(bind, "financeiro_agro_entradas"):
        op.create_table(
            "financeiro_agro_entradas",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("cliente_agro_id", sa.Integer(), nullable=True),
            sa.Column("categoria", sa.String(length=120), nullable=False),
            sa.Column("descricao", sa.String(length=180), nullable=False),
            sa.Column("cliente_nome", sa.String(length=150), nullable=False),
            sa.Column("cep", sa.String(length=9), nullable=True),
            sa.Column("logradouro", sa.String(length=150), nullable=True),
            sa.Column("numero", sa.String(length=20), nullable=True),
            sa.Column("complemento", sa.String(length=100), nullable=True),
            sa.Column("bairro", sa.String(length=100), nullable=True),
            sa.Column("cidade", sa.String(length=100), nullable=True),
            sa.Column("uf", sa.String(length=2), nullable=True),
            sa.Column("forma_recebimento", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDENTE"),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("competencia_mes", sa.Integer(), nullable=True),
            sa.Column("competencia_ano", sa.Integer(), nullable=True),
            sa.Column("data_lancamento", sa.Date(), nullable=True),
            sa.Column("data_vencimento", sa.Date(), nullable=False),
            sa.Column("data_recebimento", sa.Date(), nullable=True),
            sa.Column("valor", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["cliente_agro_id"], ["clientes_agro.id"]),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

        op.create_index(op.f("ix_financeiro_agro_entradas_id"), "financeiro_agro_entradas", ["id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_prefeitura_id"), "financeiro_agro_entradas", ["prefeitura_id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_cliente_agro_id"), "financeiro_agro_entradas", ["cliente_agro_id"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_categoria"), "financeiro_agro_entradas", ["categoria"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_cliente_nome"), "financeiro_agro_entradas", ["cliente_nome"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_bairro"), "financeiro_agro_entradas", ["bairro"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_cidade"), "financeiro_agro_entradas", ["cidade"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_uf"), "financeiro_agro_entradas", ["uf"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_status"), "financeiro_agro_entradas", ["status"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_competencia_mes"), "financeiro_agro_entradas", ["competencia_mes"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_competencia_ano"), "financeiro_agro_entradas", ["competencia_ano"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_data_lancamento"), "financeiro_agro_entradas", ["data_lancamento"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_data_vencimento"), "financeiro_agro_entradas", ["data_vencimento"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_data_recebimento"), "financeiro_agro_entradas", ["data_recebimento"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_criado_em"), "financeiro_agro_entradas", ["criado_em"], unique=False)
        op.create_index(op.f("ix_financeiro_agro_entradas_atualizado_em"), "financeiro_agro_entradas", ["atualizado_em"], unique=False)
        op.create_index("ix_financeiro_agro_entradas_competencia", "financeiro_agro_entradas", ["competencia_ano", "competencia_mes"], unique=False)
        op.create_index("ix_financeiro_agro_entradas_status_vencimento", "financeiro_agro_entradas", ["status", "data_vencimento"], unique=False)
        op.create_index("ix_financeiro_agro_entradas_categoria_status", "financeiro_agro_entradas", ["categoria", "status"], unique=False)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_entradas"):
        op.drop_index("ix_financeiro_agro_entradas_categoria_status", table_name="financeiro_agro_entradas")
        op.drop_index("ix_financeiro_agro_entradas_status_vencimento", table_name="financeiro_agro_entradas")
        op.drop_index("ix_financeiro_agro_entradas_competencia", table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_atualizado_em"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_criado_em"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_data_recebimento"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_data_vencimento"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_data_lancamento"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_competencia_ano"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_competencia_mes"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_status"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_uf"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_cidade"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_bairro"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_cliente_nome"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_categoria"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_cliente_agro_id"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_prefeitura_id"), table_name="financeiro_agro_entradas")
        op.drop_index(op.f("ix_financeiro_agro_entradas_id"), table_name="financeiro_agro_entradas")
        op.drop_table("financeiro_agro_entradas")

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "uf" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_uf"))
                batch_op.drop_column("uf")
            if "cidade" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_cidade"))
                batch_op.drop_column("cidade")
            if "bairro" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_bairro"))
                batch_op.drop_column("bairro")
            if "complemento" in columns:
                batch_op.drop_column("complemento")
            if "numero" in columns:
                batch_op.drop_column("numero")
            if "logradouro" in columns:
                batch_op.drop_column("logradouro")
            if "cep" in columns:
                batch_op.drop_column("cep")
            if "cliente_agro_id" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_cliente_agro_id"))
                batch_op.drop_constraint("fk_financeiro_agro_saidas_cliente_agro_id", type_="foreignkey")
                batch_op.drop_column("cliente_agro_id")
