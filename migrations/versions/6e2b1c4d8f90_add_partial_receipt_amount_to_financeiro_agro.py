"""add partial receipt amount to financeiro agro

Revision ID: 6e2b1c4d8f90
Revises: f29d7c41a6b8
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "6e2b1c4d8f90"
down_revision = "f29d7c41a6b8"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name, column_name):
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("financeiro_agro") and not _has_column(inspector, "financeiro_agro", "valor_recebido"):
        op.add_column(
            "financeiro_agro",
            sa.Column("valor_recebido", sa.Numeric(12, 2), nullable=False, server_default="0"),
        )
        op.alter_column("financeiro_agro", "valor_recebido", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("financeiro_agro") and _has_column(inspector, "financeiro_agro", "valor_recebido"):
        op.drop_column("financeiro_agro", "valor_recebido")
