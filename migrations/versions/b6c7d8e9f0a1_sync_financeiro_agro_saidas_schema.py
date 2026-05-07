"""sync financeiro agro saidas schema

Revision ID: b6c7d8e9f0a1
Revises: a9f4d1c2b3e8
Create Date: 2026-05-07 12:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b6c7d8e9f0a1"
down_revision = "a9f4d1c2b3e8"
branch_labels = None
depends_on = None


TABLE_NAME = "financeiro_agro_saidas"


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {fk.get("name") for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def _create_index_if_missing(batch_op, existing_indexes, index_name, columns):
    if index_name not in existing_indexes:
        batch_op.create_index(index_name, columns, unique=False)


def _create_foreign_key_if_possible(batch_op, existing_fks, fk_name, referent_table, local_cols, remote_cols):
    if fk_name not in existing_fks:
        batch_op.create_foreign_key(fk_name, referent_table, local_cols, remote_cols)


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, TABLE_NAME):
        return

    columns = _column_names(bind, TABLE_NAME)
    indexes = _index_names(bind, TABLE_NAME)
    foreign_keys = _foreign_key_names(bind, TABLE_NAME)
    has_clientes = _table_exists(bind, "clientes_agro")
    has_fornecedores = _table_exists(bind, "fornecedores_agro")
    has_bancos = _table_exists(bind, "banco_agro")

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        added_cliente_agro_id = "cliente_agro_id" not in columns
        if added_cliente_agro_id:
            batch_op.add_column(sa.Column("cliente_agro_id", sa.Integer(), nullable=True))
        _create_index_if_missing(
            batch_op,
            indexes,
            "ix_financeiro_agro_saidas_cliente_agro_id",
            ["cliente_agro_id"],
        )
        if added_cliente_agro_id and has_clientes:
            _create_foreign_key_if_possible(
                batch_op,
                foreign_keys,
                "fk_financeiro_agro_saidas_cliente_agro_id",
                "clientes_agro",
                ["cliente_agro_id"],
                ["id"],
            )

        added_fornecedor_agro_id = "fornecedor_agro_id" not in columns
        if added_fornecedor_agro_id:
            batch_op.add_column(sa.Column("fornecedor_agro_id", sa.Integer(), nullable=True))
        _create_index_if_missing(
            batch_op,
            indexes,
            "ix_financeiro_agro_saidas_fornecedor_agro_id",
            ["fornecedor_agro_id"],
        )
        if added_fornecedor_agro_id and has_fornecedores:
            _create_foreign_key_if_possible(
                batch_op,
                foreign_keys,
                "fk_financeiro_agro_saidas_fornecedor_agro_id",
                "fornecedores_agro",
                ["fornecedor_agro_id"],
                ["id"],
            )

        added_banco_agro_id = "banco_agro_id" not in columns
        if added_banco_agro_id:
            batch_op.add_column(sa.Column("banco_agro_id", sa.Integer(), nullable=True))
        _create_index_if_missing(
            batch_op,
            indexes,
            "ix_financeiro_agro_saidas_banco_agro_id",
            ["banco_agro_id"],
        )
        if added_banco_agro_id and has_bancos:
            _create_foreign_key_if_possible(
                batch_op,
                foreign_keys,
                "fk_financeiro_agro_saidas_banco_agro_id_bancos_agro",
                "banco_agro",
                ["banco_agro_id"],
                ["id"],
            )

        if "subcategoria" not in columns:
            batch_op.add_column(sa.Column("subcategoria", sa.String(length=120), nullable=True))
        _create_index_if_missing(batch_op, indexes, "ix_financeiro_agro_saidas_subcategoria", ["subcategoria"])

        if "documento_referencia" not in columns:
            batch_op.add_column(sa.Column("documento_referencia", sa.String(length=80), nullable=True))
        _create_index_if_missing(
            batch_op,
            indexes,
            "ix_financeiro_agro_saidas_documento_referencia",
            ["documento_referencia"],
        )

        if "detalhamento_imposto" not in columns:
            batch_op.add_column(sa.Column("detalhamento_imposto", sa.String(length=180), nullable=True))
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
        _create_index_if_missing(batch_op, indexes, "ix_financeiro_agro_saidas_bairro", ["bairro"])

        if "cidade" not in columns:
            batch_op.add_column(sa.Column("cidade", sa.String(length=100), nullable=True))
        _create_index_if_missing(batch_op, indexes, "ix_financeiro_agro_saidas_cidade", ["cidade"])

        if "uf" not in columns:
            batch_op.add_column(sa.Column("uf", sa.String(length=2), nullable=True))
        _create_index_if_missing(batch_op, indexes, "ix_financeiro_agro_saidas_uf", ["uf"])

        if "data_emissao" not in columns:
            batch_op.add_column(sa.Column("data_emissao", sa.Date(), nullable=True))
        _create_index_if_missing(batch_op, indexes, "ix_financeiro_agro_saidas_data_emissao", ["data_emissao"])

        if "grupo_lancamento" not in columns:
            batch_op.add_column(sa.Column("grupo_lancamento", sa.String(length=36), nullable=True))
        _create_index_if_missing(
            batch_op,
            indexes,
            "ix_financeiro_agro_saidas_grupo_lancamento",
            ["grupo_lancamento"],
        )

        if "parcela_numero" not in columns:
            batch_op.add_column(sa.Column("parcela_numero", sa.Integer(), nullable=False, server_default="1"))
        if "parcela_total" not in columns:
            batch_op.add_column(sa.Column("parcela_total", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    pass
