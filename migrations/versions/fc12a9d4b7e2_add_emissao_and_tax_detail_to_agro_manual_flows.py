"""add emissao and tax detail to agro manual flows

Revision ID: fc12a9d4b7e2
Revises: fb82d1c4e6a9
Create Date: 2026-04-15 16:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fc12a9d4b7e2"
down_revision = "fb82d1c4e6a9"
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
            if "documento_referencia" not in columns:
                batch_op.add_column(sa.Column("documento_referencia", sa.String(length=80), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_entradas_documento_referencia"), ["documento_referencia"], unique=False)
            if "data_emissao" not in columns:
                batch_op.add_column(sa.Column("data_emissao", sa.Date(), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_entradas_data_emissao"), ["data_emissao"], unique=False)

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "documento_referencia" not in columns:
                batch_op.add_column(sa.Column("documento_referencia", sa.String(length=80), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_documento_referencia"), ["documento_referencia"], unique=False)
            if "detalhamento_imposto" not in columns:
                batch_op.add_column(sa.Column("detalhamento_imposto", sa.String(length=180), nullable=True))
            if "data_emissao" not in columns:
                batch_op.add_column(sa.Column("data_emissao", sa.Date(), nullable=True))
                batch_op.create_index(batch_op.f("ix_financeiro_agro_saidas_data_emissao"), ["data_emissao"], unique=False)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "financeiro_agro_saidas"):
        columns = _column_names(bind, "financeiro_agro_saidas")
        with op.batch_alter_table("financeiro_agro_saidas", schema=None) as batch_op:
            if "data_emissao" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_data_emissao"))
                batch_op.drop_column("data_emissao")
            if "detalhamento_imposto" in columns:
                batch_op.drop_column("detalhamento_imposto")
            if "documento_referencia" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_saidas_documento_referencia"))
                batch_op.drop_column("documento_referencia")

    if _table_exists(bind, "financeiro_agro_entradas"):
        columns = _column_names(bind, "financeiro_agro_entradas")
        with op.batch_alter_table("financeiro_agro_entradas", schema=None) as batch_op:
            if "data_emissao" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_entradas_data_emissao"))
                batch_op.drop_column("data_emissao")
            if "documento_referencia" in columns:
                batch_op.drop_index(batch_op.f("ix_financeiro_agro_entradas_documento_referencia"))
                batch_op.drop_column("documento_referencia")
