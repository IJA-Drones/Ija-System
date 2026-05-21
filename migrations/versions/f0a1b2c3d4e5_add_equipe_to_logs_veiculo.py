"""add equipe to logs veiculo

Revision ID: f0a1b2c3d4e5
Revises: e7b4c2d9f1a3
Create Date: 2026-05-21 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e7b4c2d9f1a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("equipe_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_logs_veiculo_equipe_id", "equipes", ["equipe_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_logs_veiculo_equipe_id"), ["equipe_id"], unique=False)


def downgrade():
    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_logs_veiculo_equipe_id"))
        batch_op.drop_constraint("fk_logs_veiculo_equipe_id", type_="foreignkey")
        batch_op.drop_column("equipe_id")
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
