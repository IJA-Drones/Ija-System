"""Persist company identity and logos independently of finance records."""
from alembic import op
import sqlalchemy as sa

revision = "d8a210bf7c35"
down_revision = "c4d71a02e6b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("financeiro_empresa_perfis",
        sa.Column("empresa_slug", sa.String(80), primary_key=True),
        sa.Column("nome", sa.String(120)),
        sa.Column("razao_social", sa.String(180)),
        sa.Column("cnpj", sa.String(14), unique=True),
        sa.Column("logo", sa.LargeBinary()),
        sa.Column("tem_logo", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_table("financeiro_empresa_perfis")
