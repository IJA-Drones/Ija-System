"""add mapa aplicacao fields to agro os

Revision ID: e8b1c2d3f4a5
Revises: c2d3e4f5a6b7, d4f6a8b0c2e4
Create Date: 2026-04-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "e8b1c2d3f4a5"
down_revision = ("c2d3e4f5a6b7", "d4f6a8b0c2e4")
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table("ordens_servico_agro", schema=None) as batch_op:
        if not _column_exists(conn, "ordens_servico_agro", "mapa_aplicacao_path"):
            batch_op.add_column(sa.Column("mapa_aplicacao_path", sa.String(length=255), nullable=True))
        if not _column_exists(conn, "ordens_servico_agro", "mapa_aplicacao_nome"):
            batch_op.add_column(sa.Column("mapa_aplicacao_nome", sa.String(length=255), nullable=True))


def downgrade():
    op.execute(text("ALTER TABLE ordens_servico_agro DROP COLUMN IF EXISTS mapa_aplicacao_path"))
    op.execute(text("ALTER TABLE ordens_servico_agro DROP COLUMN IF EXISTS mapa_aplicacao_nome"))
