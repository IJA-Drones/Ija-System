"""add tipo_imovel to solicitacoes

Revision ID: d9a7c3b1f2e4
Revises: c4b3a2d1e0f9
Create Date: 2026-04-13 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "d9a7c3b1f2e4"
down_revision = "c4b3a2d1e0f9"
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
    columns = _column_names(conn, "solicitacoes")
    indexes = _index_names(conn, "solicitacoes")
    index_name = op.f("ix_solicitacoes_tipo_imovel")

    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        if "tipo_imovel" not in columns:
            batch_op.add_column(sa.Column("tipo_imovel", sa.String(length=30), nullable=True))
        if index_name not in indexes:
            batch_op.create_index(index_name, ["tipo_imovel"], unique=False)


def downgrade():
    conn = op.get_bind()
    columns = _column_names(conn, "solicitacoes")
    indexes = _index_names(conn, "solicitacoes")
    index_name = op.f("ix_solicitacoes_tipo_imovel")

    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        if index_name in indexes:
            batch_op.drop_index(index_name)
        if "tipo_imovel" in columns:
            batch_op.drop_column("tipo_imovel")
