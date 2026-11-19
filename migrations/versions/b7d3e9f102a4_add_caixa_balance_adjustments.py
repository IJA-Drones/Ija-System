"""Keep permanent, transactional history of daily opening balance adjustments."""
from alembic import op
import sqlalchemy as sa

revision = "b7d3e9f102a4"
down_revision = "a3e5c7d901b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financeiro_agro_caixa_ajustes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("caixa_id", sa.Integer(), sa.ForeignKey("financeiro_agro_caixa_diario.id"), nullable=False),
        sa.Column("saldo_anterior", sa.Numeric(12, 2), nullable=False),
        sa.Column("saldo_novo", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(1000), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("usuario_nome", sa.String(120), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_financeiro_agro_caixa_ajustes_caixa_id", "financeiro_agro_caixa_ajustes", ["caixa_id"])


def downgrade():
    op.drop_table("financeiro_agro_caixa_ajustes")
