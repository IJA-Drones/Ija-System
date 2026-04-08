"""add regiao_alternativa to pilotos

Revision ID: d91f4a7c2b10
Revises: b4d1c2e9f301
Create Date: 2026-04-08 10:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d91f4a7c2b10"
down_revision = "b4d1c2e9f301"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name, column_name):
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("pilotos") and not _has_column(inspector, "pilotos", "regiao_alternativa"):
        with op.batch_alter_table("pilotos", schema=None) as batch_op:
            batch_op.add_column(sa.Column("regiao_alternativa", sa.String(length=20), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("pilotos") and _has_column(inspector, "pilotos", "regiao_alternativa"):
        with op.batch_alter_table("pilotos", schema=None) as batch_op:
            batch_op.drop_column("regiao_alternativa")

