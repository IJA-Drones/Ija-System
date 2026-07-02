"""add_status_to_equipe_uvis_os

Revision ID: b7c8d9e0f1a2
Revises: f6a1b2c3d4e5
Create Date: 2026-07-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ordens_servico_equipe_uvis") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="EM_ANDAMENTO",
            )
        )
        batch_op.create_index(
            batch_op.f("ix_ordens_servico_equipe_uvis_status"),
            ["status"],
            unique=False,
        )

    with op.batch_alter_table("ordens_servico_equipe_uvis") as batch_op:
        batch_op.alter_column("status", server_default=None)


def downgrade():
    with op.batch_alter_table("ordens_servico_equipe_uvis") as batch_op:
        batch_op.drop_index(batch_op.f("ix_ordens_servico_equipe_uvis_status"))
        batch_op.drop_column("status")
