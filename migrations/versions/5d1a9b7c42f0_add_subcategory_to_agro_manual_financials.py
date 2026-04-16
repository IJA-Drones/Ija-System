"""add subcategory to agro manual financials

Revision ID: 5d1a9b7c42f0
Revises: 7b3f2c1a8d44
Create Date: 2026-04-16 13:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "5d1a9b7c42f0"
down_revision = "7b3f2c1a8d44"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_names(bind, table_name):
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_entradas"):
        columns = _column_names(bind, "financeiro_agro_entradas")
        with op.batch_alter_table("financeiro_agro_entradas", schema=None) as batch_op:
            if "subcategoria" not in columns:
                batch_op.add_column(sa.Column("subcategoria", sa.String(length=120), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_entradas_subcategoria"), ["subcategoria"], unique=False)

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "subcategoria" not in columns:
                batch_op.add_column(sa.Column("subcategoria", sa.String(length=120), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_subcategoria"), ["subcategoria"], unique=False)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "subcategoria" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_subcategoria"))
                batch_op.drop_column("subcategoria")

    if _table_exists(bind, "financeiro_agro_entradas"):
        columns = _column_names(bind, "financeiro_agro_entradas")
        with op.batch_alter_table("financeiro_agro_entradas", schema=None) as batch_op:
            if "subcategoria" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_entradas_subcategoria"))
                batch_op.drop_column("subcategoria")
