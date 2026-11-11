"""Add technician signatures to equipment maintenance reports."""
from alembic import op
import sqlalchemy as sa


revision = "f7c1d9a4e602"
down_revision = "e9c5b2a7d014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "manutencoes_equipamentos",
        sa.Column("assinatura_responsavel_tecnico", sa.Text(), nullable=True),
    )
    op.add_column(
        "manutencoes_equipamentos",
        sa.Column("assinatura_responsavel_avaria", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("manutencoes_equipamentos", "assinatura_responsavel_avaria")
    op.drop_column("manutencoes_equipamentos", "assinatura_responsavel_tecnico")
