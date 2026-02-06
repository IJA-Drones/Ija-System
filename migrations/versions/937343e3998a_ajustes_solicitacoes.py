"""ajustes solicitacoes

Revision ID: 937343e3998a
Revises: c956444eccf2
Create Date: 2025-xx-xx xx:xx:xx.xxxxxx
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "937343e3998a"
down_revision = "c956444eccf2"
branch_labels = None
depends_on = None

def _column_exists(conn, table: str, column: str, schema: str = "public") -> bool:
    return conn.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
        """),
        {"schema": schema, "table": table, "column": column},
    ).scalar() is not None


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        if not _column_exists(conn, "solicitacoes", "equipe_id"):
            batch_op.add_column(sa.Column("equipe_id", sa.Integer(), nullable=True))