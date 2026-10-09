"""track admin response visualization for quadra requests

Revision ID: f1a2b3c4d5e6
Revises: 17c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "17c3d4e5f6a7"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("solicitacoes", sa.Column("quadra_visualizada_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("solicitacoes", sa.Column("quadra_visualizada_admin_em", sa.DateTime(), nullable=True))
    op.alter_column("solicitacoes", "quadra_visualizada_admin", server_default=None)

def downgrade():
    op.drop_column("solicitacoes", "quadra_visualizada_admin_em")
    op.drop_column("solicitacoes", "quadra_visualizada_admin")
