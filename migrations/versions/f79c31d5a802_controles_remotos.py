"""Cadastro de controles remotos vinculado à hierarquia dos drones."""
from alembic import op
import sqlalchemy as sa

revision = "f79c31d5a802"
down_revision = "e64b1d9f203a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("controles_remotos",
        sa.Column("id", sa.Integer(), sa.ForeignKey("equipamentos.id"), primary_key=True),
        sa.Column("drone_id", sa.Integer(), sa.ForeignKey("drones.id", ondelete="RESTRICT"), nullable=False),
    )
    op.create_index("ix_controles_remotos_drone_id", "controles_remotos", ["drone_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM controles_remotos LIMIT 1")).first():
        raise RuntimeError("Há controles cadastrados. Preserve ou remova esses registros antes de reverter a migração.")
    op.drop_table("controles_remotos")
