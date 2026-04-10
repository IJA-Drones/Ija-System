"""add preco_base to orcamentos_agro

Revision ID: f4c8d2a1b6e0
Revises: e3b7a9c4d2f1
Create Date: 2026-04-08 16:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f4c8d2a1b6e0"
down_revision = "e3b7a9c4d2f1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preco_base", sa.Numeric(precision=12, scale=2), nullable=True))

    op.execute("UPDATE orcamentos_agro SET preco_base = 0 WHERE preco_base IS NULL")

    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.alter_column("preco_base", existing_type=sa.Numeric(precision=12, scale=2), nullable=False)


def downgrade():
    with op.batch_alter_table("orcamentos_agro", schema=None) as batch_op:
        batch_op.drop_column("preco_base")
