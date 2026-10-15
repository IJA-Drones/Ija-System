"""Track future password changes and add the DEV-managed expiration policy."""
from alembic import op
import sqlalchemy as sa

revision = "d94f2a7610be"
down_revision = "b82e0d5f314c"
branch_labels = None
depends_on = None


def upgrade():
    # No default/backfill: current passwords remain exempt until changed.
    op.add_column("usuarios", sa.Column("senha_alterada_em", sa.DateTime(), nullable=True))
    policy = op.create_table(
        "politica_senha",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("validade_dias", sa.Integer(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_politica_senha_singleton"),
        sa.CheckConstraint("validade_dias BETWEEN 1 AND 365", name="ck_politica_senha_validade"),
    )
    op.bulk_insert(policy, [{"id": 1, "validade_dias": 90}])


def downgrade():
    op.drop_table("politica_senha")
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("senha_alterada_em")
