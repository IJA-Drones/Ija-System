"""add limpezas veiculo

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
    op.create_table(
        "limpezas_veiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_veiculo_id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("piloto_id", sa.Integer(), nullable=True),
        sa.Column("equipe_id", sa.Integer(), nullable=True),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("limpeza_realizada", sa.Boolean(), nullable=False),
        sa.Column("tipo_limpeza", sa.String(length=30), nullable=False),
        sa.Column("valor_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["equipe_id"], ["equipes.id"]),
        sa.ForeignKeyConstraint(["log_veiculo_id"], ["logs_veiculo.id"]),
        sa.ForeignKeyConstraint(["piloto_id"], ["pilotos.id"]),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_data_hora"), ["data_hora"], unique=False)
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_equipe_id"), ["equipe_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_log_veiculo_id"), ["log_veiculo_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_piloto_id"), ["piloto_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_limpezas_veiculo_veiculo_id"), ["veiculo_id"], unique=False)


def downgrade():
    with op.batch_alter_table("limpezas_veiculo", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_veiculo_id"))
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_piloto_id"))
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_log_veiculo_id"))
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_equipe_id"))
        batch_op.drop_index(batch_op.f("ix_limpezas_veiculo_data_hora"))

    op.drop_table("limpezas_veiculo")
