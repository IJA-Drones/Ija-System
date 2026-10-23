"""contatos públicos: campo de serviços sem limite de 1500

Revision ID: 9c5309bacdd0
Revises: 2283da228381
"""
from alembic import op
import sqlalchemy as sa

revision = "9c5309bacdd0"
down_revision = "2283da228381"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("prefeitura_contatos_publicos") as batch:
        batch.alter_column("servicos", type_=sa.Text(), existing_type=sa.String(1500), existing_nullable=False)


def downgrade():
    with op.batch_alter_table("prefeitura_contatos_publicos") as batch:
        batch.alter_column("servicos", type_=sa.String(1500), existing_type=sa.Text(), existing_nullable=False)
