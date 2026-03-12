"""abastecimentos por turno

Revision ID: b8a7d2956a11
Revises: c6925a2c28d0
Create Date: 2026-03-12 12:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8a7d2956a11"
down_revision = "c6925a2c28d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "abastecimentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_veiculo_id", sa.Integer(), nullable=False),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("km_registro", sa.Float(), nullable=False),
        sa.Column("litros", sa.Float(), nullable=False),
        sa.Column("valor_total", sa.Float(), nullable=True),
        sa.Column("foto_nf_path", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["log_veiculo_id"], ["logs_veiculo.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("abastecimentos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_abastecimentos_log_veiculo_id"), ["log_veiculo_id"], unique=False)

    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.drop_column("km_no_abastecimento")
        batch_op.drop_column("foto_nf_path")
        batch_op.drop_column("valor_total")
        batch_op.drop_column("litros")
        batch_op.drop_column("abasteceu")


def downgrade():
    with op.batch_alter_table("logs_veiculo", schema=None) as batch_op:
        batch_op.add_column(sa.Column("abasteceu", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("litros", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("valor_total", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("foto_nf_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("km_no_abastecimento", sa.Float(), nullable=True))

    with op.batch_alter_table("abastecimentos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_abastecimentos_log_veiculo_id"))

    op.drop_table("abastecimentos")
