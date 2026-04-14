"""rename camilo columns in financeiro agro

Revision ID: f3c8b2a1d4e5
Revises: e7a1c4f9b2d3
Create Date: 2026-04-13 14:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f3c8b2a1d4e5"
down_revision = "e7a1c4f9b2d3"
branch_labels = None
depends_on = None


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    columns = _column_names(bind, "financeiro_agro")

    with op.batch_alter_table("financeiro_agro", schema=None) as batch_op:
        if "comissao_camilo_por_ha" in columns and "comissao_por_ha" not in columns:
            batch_op.alter_column(
                "comissao_camilo_por_ha",
                new_column_name="comissao_por_ha",
                existing_type=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
                existing_server_default="8",
            )
        if "valor_comissao_camilo" in columns and "valor_comissao" not in columns:
            batch_op.alter_column(
                "valor_comissao_camilo",
                new_column_name="valor_comissao",
                existing_type=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
                existing_server_default="0",
            )


def downgrade():
    bind = op.get_bind()
    columns = _column_names(bind, "financeiro_agro")

    with op.batch_alter_table("financeiro_agro", schema=None) as batch_op:
        if "comissao_por_ha" in columns and "comissao_camilo_por_ha" not in columns:
            batch_op.alter_column(
                "comissao_por_ha",
                new_column_name="comissao_camilo_por_ha",
                existing_type=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
                existing_server_default="8",
            )
        if "valor_comissao" in columns and "valor_comissao_camilo" not in columns:
            batch_op.alter_column(
                "valor_comissao",
                new_column_name="valor_comissao_camilo",
                existing_type=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
                existing_server_default="0",
            )
