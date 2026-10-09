"""merge the existing migration head with the quadra migration

Revision ID: 17c3d4e5f6a7
Revises: 16b2b6ff2719, fe12a9b3c4d5
"""
from alembic import op

revision = "17c3d4e5f6a7"
down_revision = ("16b2b6ff2719", "fe12a9b3c4d5")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
