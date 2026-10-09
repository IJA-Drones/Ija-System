"""Add Skybox path before transferring existing company logos."""
from alembic import op
import sqlalchemy as sa
revision = "e2b431cc9f70"
down_revision = "d8a210bf7c35"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("financeiro_empresa_perfis", sa.Column("logo_path", sa.String(500), nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM financeiro_empresa_perfis WHERE logo_path IS NOT NULL")).scalar():
        raise RuntimeError("Existem logos no Skybox. Preserve os caminhos antes de reverter.")
    op.drop_column("financeiro_empresa_perfis", "logo_path")
