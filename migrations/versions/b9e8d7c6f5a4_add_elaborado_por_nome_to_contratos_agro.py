"""add elaborado_por_nome to contratos agro

Revision ID: b9e8d7c6f5a4
Revises: a8c7d6e5f4b3
Create Date: 2026-04-10 14:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "b9e8d7c6f5a4"
down_revision = "a8c7d6e5f4b3"
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
    columns = _column_names(conn, "contratos_agro")
    indexes = _index_names(conn, "contratos_agro")
    index_name = op.f("ix_contratos_agro_elaborado_por_nome")

    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        if "elaborado_por_nome" not in columns:
            batch_op.add_column(sa.Column("elaborado_por_nome", sa.String(length=150), nullable=True))
        if index_name not in indexes:
            batch_op.create_index(index_name, ["elaborado_por_nome"], unique=False)


def downgrade():
    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_contratos_agro_elaborado_por_nome"))
        batch_op.drop_column("elaborado_por_nome")
