"""add embreagem e freios to checklists veiculo

Revision ID: a6d4e2b8c9f1
Revises: a1c9d8e7f6b5
Create Date: 2026-09-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a6d4e2b8c9f1"
down_revision = "a1c9d8e7f6b5"
branch_labels = None
depends_on = None


def upgrade():
    # Inicializa os novos itens com o padrão funcional usado pelo checklist.
    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("embreagem", sa.Boolean(), nullable=True, server_default=sa.true()))
        batch_op.add_column(sa.Column("freio_mao", sa.Boolean(), nullable=True, server_default=sa.true()))
        batch_op.add_column(sa.Column("freio_pe", sa.Boolean(), nullable=True, server_default=sa.true()))
        batch_op.add_column(sa.Column("condicao_embreagem_freios", sa.Text(), nullable=True))

    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.alter_column("embreagem", existing_type=sa.Boolean(), server_default=None)
        batch_op.alter_column("freio_mao", existing_type=sa.Boolean(), server_default=None)
        batch_op.alter_column("freio_pe", existing_type=sa.Boolean(), server_default=None)


def downgrade():
    with op.batch_alter_table("checklists_semanais_veiculo", schema=None) as batch_op:
        batch_op.drop_column("condicao_embreagem_freios")
        batch_op.drop_column("freio_pe")
        batch_op.drop_column("freio_mao")
        batch_op.drop_column("embreagem")
