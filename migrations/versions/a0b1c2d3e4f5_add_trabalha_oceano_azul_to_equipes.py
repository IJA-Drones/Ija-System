"""add trabalha oceano azul to equipes

Revision ID: a0b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-07-30 11:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a0b1c2d3e4f5"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("equipes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "trabalha_oceano_azul",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.create_index(
            batch_op.f("ix_equipes_trabalha_oceano_azul"),
            ["trabalha_oceano_azul"],
            unique=False,
        )

    op.execute("UPDATE equipes SET trabalha_oceano_azul = TRUE")
    op.execute("UPDATE usuarios SET trabalha_oceano_azul = TRUE WHERE tipo_usuario = 'equipe_oceano'")


def downgrade():
    op.execute("UPDATE usuarios SET trabalha_oceano_azul = FALSE WHERE tipo_usuario = 'equipe_oceano'")

    with op.batch_alter_table("equipes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipes_trabalha_oceano_azul"))
        batch_op.drop_column("trabalha_oceano_azul")
