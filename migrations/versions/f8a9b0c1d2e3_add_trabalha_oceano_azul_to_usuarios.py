"""add trabalha oceano azul to usuarios

Revision ID: f8a9b0c1d2e3
Revises: e2f3a4b5c6d7
Create Date: 2026-07-30 11:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "trabalha_oceano_azul",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(
            batch_op.f("ix_usuarios_trabalha_oceano_azul"),
            ["trabalha_oceano_azul"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_usuarios_trabalha_oceano_azul"))
        batch_op.drop_column("trabalha_oceano_azul")
