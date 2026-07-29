"""add limpeza to checklists semanais

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-07-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "limpeza_veiculo_realizada",
                sa.Boolean(),
                nullable=True,
                server_default=sa.true(),
            )
        )

    with op.batch_alter_table("checklists_semanais_drone", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "limpeza_equipamento_realizada",
                sa.Boolean(),
                nullable=True,
                server_default=sa.true(),
            )
        )


def downgrade():
    with op.batch_alter_table("checklists_semanais_drone", schema=None) as batch_op:
        batch_op.drop_column("limpeza_equipamento_realizada")

    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.drop_column("limpeza_veiculo_realizada")
