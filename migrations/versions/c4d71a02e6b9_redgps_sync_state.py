"""Track RedGPS polling across web workers without storing credentials."""
from alembic import op
import sqlalchemy as sa

revision = "c4d71a02e6b9"
down_revision = "e15caed9908f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rastreamento_sincronizacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tentado_em", sa.DateTime()),
        sa.Column("sincronizado_em", sa.DateTime()),
        sa.Column("erro", sa.String(80)),
    )


def downgrade():
    op.drop_table("rastreamento_sincronizacao")
