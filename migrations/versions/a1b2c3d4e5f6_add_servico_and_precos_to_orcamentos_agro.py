"""add servico and preco_mapeamento to orcamentos_agro

Revision ID: a1b2c3d4e5f6
Revises: f4c8d2a1b6e0
Create Date: 2026-04-08 19:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f4c8d2a1b6e0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.add_column(sa.Column("servico", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("preco_monitoramento", sa.Numeric(precision=12, scale=2), nullable=True))
        batch_op.add_column(sa.Column("preco_pulverizacao", sa.Numeric(precision=12, scale=2), nullable=True))

    op.execute("UPDATE orcamentos_agro SET servico = 'Mapeamento' WHERE servico IS NULL")
    op.execute("UPDATE orcamentos_agro SET preco_monitoramento = 0 WHERE preco_monitoramento IS NULL")
    op.execute("UPDATE orcamentos_agro SET preco_pulverizacao = 0 WHERE preco_pulverizacao IS NULL")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.alter_column("servico", existing_type=sa.String(length=50), nullable=False)
        batch_op.alter_column("preco_monitoramento", existing_type=sa.Numeric(precision=12, scale=2), nullable=False)
        batch_op.alter_column("preco_pulverizacao", existing_type=sa.Numeric(precision=12, scale=2), nullable=False)


def downgrade():
    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.drop_column("preco_pulverizacao")
        batch_op.drop_column("preco_monitoramento")
        batch_op.drop_column("servico")
