"""add data registro to limpezas veiculo

Revision ID: e2f3a4b5c6d7
Revises: d6e7f8a9b0c1
Create Date: 2026-07-29 00:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("data_registro", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_data_registro"), ["data_registro"], unique=False)

    op.execute("UPDATE limpezas_veiculo SET data_registro = data_hora WHERE data_registro IS NULL")

    with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
        batch_op.alter_column("data_registro", existing_type=sa.DateTime(), nullable=False)


def downgrade():
    with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_data_registro"))
        batch_op.drop_column("data_registro")
