"""add da to solicitacoes

Revision ID: d5e6f7a8b9c0
Revises: b3c4d5e6f7a8
Create Date: 2026-07-15 11:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("distrito_administrativo", sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.drop_column("distrito_administrativo")
