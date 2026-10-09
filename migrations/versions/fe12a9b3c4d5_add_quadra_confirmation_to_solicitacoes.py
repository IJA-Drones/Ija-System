"""add quadra confirmation to solicitacoes

Revision ID: fe12a9b3c4d5
Revises: fd9c1a47ec4c
"""
from alembic import op
import sqlalchemy as sa

revision = "fe12a9b3c4d5"
down_revision = "fd9c1a47ec4c"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("solicitacoes", sa.Column("quadra_confirmada_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("solicitacoes", "quadra_confirmada_admin", server_default=None)

def downgrade():
    op.drop_column("solicitacoes", "quadra_confirmada_admin")
