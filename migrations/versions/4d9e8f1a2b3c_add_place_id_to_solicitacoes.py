"""add place_id to solicitacoes

Revision ID: 4d9e8f1a2b3c
Revises: 3c86bbd26982
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d9e8f1a2b3c"
down_revision = "3c86bbd26982"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("place_id", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_solicitacoes_place_id", ["place_id"], unique=False)


def downgrade():
    with op.batch_alter_table("solicitacoes", schema=None) as batch_op:
        batch_op.drop_index("ix_solicitacoes_place_id")
        batch_op.drop_column("place_id")
