"""add bancos agro and bank links to agro financials

Revision ID: 8f4c2a1b9d77
Revises: 5d1a9b7c42f0
Create Date: 2026-04-16 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "8f4c2a1b9d77"
down_revision = "5d1a9b7c42f0"
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

    if not _table_exists(bind, "banco_agro"):
        op.create_table(
            "banco_agro",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prefeitura_id", sa.Integer(), nullable=True),
            sa.Column("nome", sa.String(length=120), nullable=False),
            sa.Column("banco_nome", sa.String(length=120), nullable=False),
            sa.Column("agencia", sa.String(length=20), nullable=True),
            sa.Column("conta", sa.String(length=40), nullable=True),
            sa.Column("tipo_conta", sa.String(length=20), nullable=False, server_default="CORRENTE"),
            sa.Column("saldo_inicial", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
            sa.Column("saldo_previsto", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
            sa.Column("saldo_atual", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["prefeitura_id"], ["prefeituras.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_banco_agro_nome", "banco_agro", ["nome"], unique=False)
        op.create_index("ix_banco_agro_banco_nome", "banco_agro", ["banco_nome"], unique=False)
        op.create_index("ix_banco_agro_tipo_conta", "banco_agro", ["tipo_conta"], unique=False)
        op.create_index("ix_banco_agro_ativo", "banco_agro", ["ativo"], unique=False)
        op.create_index("ix_banco_agro_prefeitura_id", "banco_agro", ["prefeitura_id"], unique=False)
        op.create_index("ix_banco_agro_nome_ativo", "banco_agro", ["nome", "ativo"], unique=False)

    for table_name in ("financeiro_agro", "financeiro_agro_entradas", "financeiro_agro_saidas"):
        if not _table_exists(bind, table_name):
            continue
        columns = _column_names(bind, table_name)
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            if "banco_agro_id" not in columns:
                batch_op.add_column(sa.Column("banco_agro_id", sa.Integer(), nullable=True))
                batch_op.create_index(batch_op.f(f"ix_{table_name}_banco_agro_id"), ["banco_agro_id"], unique=False)
                batch_op.create_foreign_key(
                    f"fk_{table_name}_banco_agro_id_bancos_agro",
                    "banco_agro",
                    ["banco_agro_id"],
                    ["id"],
                )


def downgrade():
    bind = op.get_bind()

    for table_name in ("financeiro_agro_saidas", "financeiro_agro_entradas", "financeiro_agro"):
        if not _table_exists(bind, table_name):
            continue
        columns = _column_names(bind, table_name)
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            if "banco_agro_id" in columns:
                batch_op.drop_constraint(f"fk_{table_name}_banco_agro_id_bancos_agro", type_="foreignkey")
                batch_op.drop_index(batch_op.f(f"ix_{table_name}_banco_agro_id"))
                batch_op.drop_column("banco_agro_id")

    if _table_exists(bind, "banco_agro"):
        op.drop_index("ix_banco_agro_nome_ativo", table_name="banco_agro")
        op.drop_index("ix_banco_agro_prefeitura_id", table_name="banco_agro")
        op.drop_index("ix_banco_agro_ativo", table_name="banco_agro")
        op.drop_index("ix_banco_agro_tipo_conta", table_name="banco_agro")
        op.drop_index("ix_banco_agro_banco_nome", table_name="banco_agro")
        op.drop_index("ix_banco_agro_nome", table_name="banco_agro")
        op.drop_table("banco_agro")
