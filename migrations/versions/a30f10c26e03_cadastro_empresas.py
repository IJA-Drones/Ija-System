"""Enable explicit registration of independent company profiles."""
from alembic import op
import sqlalchemy as sa

revision = "a30f10c26e03"
down_revision = "a30f10c26e01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("financeiro_empresa_perfis", sa.Column("cadastrada", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("financeiro_empresa_perfis", "cadastrada")
