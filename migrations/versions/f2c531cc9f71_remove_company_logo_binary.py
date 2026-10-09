"""Remove binary column only after all legacy logos have been transferred."""
from alembic import op
import sqlalchemy as sa
revision = "f2c531cc9f71"
down_revision = "e2b431cc9f70"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM financeiro_empresa_perfis WHERE logo IS NOT NULL")).scalar():
        raise RuntimeError("Migre as logos primeiro: python -m scripts.migrate_company_logos_to_skybox")
    op.drop_column("financeiro_empresa_perfis", "logo")


def downgrade():
    op.add_column("financeiro_empresa_perfis", sa.Column("logo", sa.LargeBinary(), nullable=True))
