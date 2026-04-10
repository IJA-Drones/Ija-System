"""move elaborado_por_nome to orcamentos agro

Revision ID: c4b3a2d1e0f9
Revises: b9e8d7c6f5a4
Create Date: 2026-04-10 14:40:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "c4b3a2d1e0f9"
down_revision = "b9e8d7c6f5a4"
branch_labels = None
depends_on = None


def _column_names(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade():
    conn = op.get_bind()
    orcamento_columns = _column_names(conn, "orcamentos_agro")
    contrato_columns = _column_names(conn, "contratos_agro")
    orcamento_indexes = _index_names(conn, "orcamentos_agro")
    contrato_indexes = _index_names(conn, "contratos_agro")
    orcamento_index_name = op.f("ix_orcamentos_agro_elaborado_por_nome")
    contrato_index_name = op.f("ix_contratos_agro_elaborado_por_nome")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if "elaborado_por_nome" not in orcamento_columns:
            batch_op.add_column(sa.Column("elaborado_por_nome", sa.String(length=150), nullable=True))
        if orcamento_index_name not in orcamento_indexes:
            batch_op.create_index(orcamento_index_name, ["elaborado_por_nome"], unique=False)

    if "elaborado_por_nome" in contrato_columns:
        op.execute(
            """
            UPDATE orcamentos_agro AS o
            SET elaborado_por_nome = c.elaborado_por_nome
            FROM contratos_agro AS c
            WHERE c.orcamento_agro_id = o.id
              AND c.elaborado_por_nome IS NOT NULL
              AND TRIM(c.elaborado_por_nome) <> ''
              AND (o.elaborado_por_nome IS NULL OR TRIM(o.elaborado_por_nome) = '')
            """
        )

        with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
            if contrato_index_name in contrato_indexes:
                batch_op.drop_index(contrato_index_name)
            batch_op.drop_column("elaborado_por_nome")


def downgrade():
    conn = op.get_bind()
    orcamento_columns = _column_names(conn, "orcamentos_agro")
    contrato_columns = _column_names(conn, "contratos_agro")
    orcamento_indexes = _index_names(conn, "orcamentos_agro")
    contrato_indexes = _index_names(conn, "contratos_agro")
    orcamento_index_name = op.f("ix_orcamentos_agro_elaborado_por_nome")
    contrato_index_name = op.f("ix_contratos_agro_elaborado_por_nome")

    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        if "elaborado_por_nome" not in contrato_columns:
            batch_op.add_column(sa.Column("elaborado_por_nome", sa.String(length=150), nullable=True))
        if contrato_index_name not in contrato_indexes:
            batch_op.create_index(contrato_index_name, ["elaborado_por_nome"], unique=False)

    if "elaborado_por_nome" in orcamento_columns:
        op.execute(
            """
            UPDATE contratos_agro AS c
            SET elaborado_por_nome = o.elaborado_por_nome
            FROM orcamentos_agro AS o
            WHERE c.orcamento_agro_id = o.id
              AND o.elaborado_por_nome IS NOT NULL
              AND TRIM(o.elaborado_por_nome) <> ''
              AND (c.elaborado_por_nome IS NULL OR TRIM(c.elaborado_por_nome) = '')
            """
        )

        with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
            if orcamento_index_name in orcamento_indexes:
                batch_op.drop_index(orcamento_index_name)
            batch_op.drop_column("elaborado_por_nome")
