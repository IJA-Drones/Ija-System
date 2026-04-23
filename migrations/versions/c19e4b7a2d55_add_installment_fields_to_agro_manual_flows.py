"""add installment fields to agro manual flows

Revision ID: c19e4b7a2d55
Revises: 91f4a2c7d8e9
Create Date: 2026-04-22 23:55:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c19e4b7a2d55"
down_revision = "91f4a2c7d8e9"
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
            if "grupo_lancamento" not in columns:
                batch_op.add_column(sa.Column("grupo_lancamento", sa.String(length=36), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_entradas_grupo_lancamento"), ["grupo_lancamento"], unique=False)
            if "parcela_numero" not in columns:
                batch_op.add_column(sa.Column("parcela_numero", sa.Integer(), nullable=False, server_default="1"))
            if "parcela_total" not in columns:
                batch_op.add_column(sa.Column("parcela_total", sa.Integer(), nullable=False, server_default="1"))

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "grupo_lancamento" not in columns:
                batch_op.add_column(sa.Column("grupo_lancamento", sa.String(length=36), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_grupo_lancamento"), ["grupo_lancamento"], unique=False)
            if "parcela_numero" not in columns:
                batch_op.add_column(sa.Column("parcela_numero", sa.Integer(), nullable=False, server_default="1"))
            if "parcela_total" not in columns:
                batch_op.add_column(sa.Column("parcela_total", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "parcela_total" in columns:
                batch_op.drop_column("parcela_total")
            if "parcela_numero" in columns:
                batch_op.drop_column("parcela_numero")
            if "grupo_lancamento" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_grupo_lancamento"))
                batch_op.drop_column("grupo_lancamento")

    if _table_exists(bind, "financeiro_agro_entradas"):
        columns = _column_names(bind, "financeiro_agro_entradas")
        with op.batch_alter_table("financeiro_agro_entradas", schema=None) as batch_op:
            if "parcela_total" in columns:
                batch_op.drop_column("parcela_total")
            if "parcela_numero" in columns:
                batch_op.drop_column("parcela_numero")
            if "grupo_lancamento" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_entradas_grupo_lancamento"))
                batch_op.drop_column("grupo_lancamento")
