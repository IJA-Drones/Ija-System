"""make orcamento cliente optional and add snapshot document

Revision ID: a8c7d6e5f4b3
Revises: f7b6c5d4e3a2
Create Date: 2026-04-10 13:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "a8c7d6e5f4b3"
down_revision = "f7b6c5d4e3a2"
branch_labels = None
depends_on = None


def _column_names(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    conn = op.get_bind()
    columns = _column_names(conn, "orcamentos_agro")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        if "cliente_documento" not in columns:
            batch_op.add_column(sa.Column("cliente_documento", sa.String(length=50), nullable=True))
            batch_op.create_index(batch_op.f("ix_orcamentos_agro_cliente_documento"), ["cliente_documento"], unique=False)

        batch_op.alter_column(
            "cliente_agro_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.alter_column(
            "cliente_agro_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.drop_index(batch_op.f("ix_orcamentos_agro_cliente_documento"))
        batch_op.drop_column("cliente_documento")
