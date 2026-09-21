"""unificar tres heads

Revision ID: d6304a5d4c0d
Revises: 68a65e96dbfc, b7c1e4f2a9d6, f1a2b3c4d5e6
Create Date: 2026-09-21 11:26:45.122475

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6304a5d4c0d'
down_revision = ('68a65e96dbfc', 'b7c1e4f2a9d6', 'f1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
