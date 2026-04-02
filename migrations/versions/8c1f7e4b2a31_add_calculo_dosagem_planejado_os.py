"""add calculo dosagem planejado os

Revision ID: 8c1f7e4b2a31
Revises: 4f8c2e1a9b7d
Create Date: 2026-04-02 10:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c1f7e4b2a31"
down_revision = "4f8c2e1a9b7d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.add_column(sa.Column("calculo_dosagem_planejado", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("calculo_dosagem_planejado_em", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_ordens_servico_calculo_dosagem_planejado_em"),
            ["calculo_dosagem_planejado_em"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("ordens_servico", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ordens_servico_calculo_dosagem_planejado_em"))
        batch_op.drop_column("calculo_dosagem_planejado_em")
        batch_op.drop_column("calculo_dosagem_planejado")
