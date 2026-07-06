"""drop legacy solicitacoes route_kml

Revision ID: e0f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2026-07-06 00:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e0f1a2b3c4d5"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def _column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if _column_exists("solicitacoes", "route_kml"):
        op.drop_column("solicitacoes", "route_kml")


def downgrade():
    if not _column_exists("solicitacoes", "route_kml"):
        op.add_column("solicitacoes", sa.Column("route_kml", sa.Text(), nullable=True))
