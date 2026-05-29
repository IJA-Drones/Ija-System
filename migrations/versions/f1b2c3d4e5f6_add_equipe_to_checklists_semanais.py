"""add equipe to checklists semanais

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-05-21 10:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("equipe_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_checklists_semanais_veiculo_equipe_id", "equipes", ["equipe_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_checklists_semanais_veiculo_equipe_id"), ["equipe_id"], unique=False)

    with op.batch_alter_table("checklists_semanais_drone", schema=None) as batch_op:
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("equipe_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_checklists_semanais_drone_equipe_id", "equipes", ["equipe_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_checklists_semanais_drone_equipe_id"), ["equipe_id"], unique=False)


def downgrade():
    with op.batch_alter_table("checklists_semanais_drone", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklists_semanais_drone_equipe_id"))
        batch_op.drop_constraint("fk_checklists_semanais_drone_equipe_id", type_="foreignkey")
        batch_op.drop_column("equipe_id")
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklists_semanais_veiculo_equipe_id"))
        batch_op.drop_constraint("fk_checklists_semanais_veiculo_equipe_id", type_="foreignkey")
        batch_op.drop_column("equipe_id")
        batch_op.alter_column(
            "piloto_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
