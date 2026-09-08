"""add trabalha agro to usuarios

Revision ID: a1c9d8e7f6b5
Revises: f8a9b0c1d2e3, c5d8e2f7a9b3
Create Date: 2026-09-08 11:58:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a1c9d8e7f6b5"
down_revision = ("f8a9b0c1d2e3", "c5d8e2f7a9b3")
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "trabalha_agro",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(
            batch_op.f("ix_usuarios_trabalha_agro"),
            ["trabalha_agro"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_usuarios_trabalha_agro"))
        batch_op.drop_column("trabalha_agro")
