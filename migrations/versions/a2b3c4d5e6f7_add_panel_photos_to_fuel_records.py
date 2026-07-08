"""add panel photos to fuel records

Revision ID: a2b3c4d5e6f7
Revises: e0f1a2b3c4d5
Create Date: 2026-07-08 09:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("foto_painel_final_path", sa.String(length=255), nullable=True))

    with op.batch_alter_table("abastecimentos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("foto_painel_path", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("abastecimentos", schema=None) as batch_op:
        batch_op.drop_column("foto_painel_path")

    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.drop_column("foto_painel_final_path")
