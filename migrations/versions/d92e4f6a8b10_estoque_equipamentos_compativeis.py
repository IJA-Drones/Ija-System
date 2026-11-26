"""Permite compartilhar uma peça entre vários equipamentos compatíveis."""
from alembic import op
import sqlalchemy as sa

revision = "d92e4f6a8b10"
down_revision = "c81f0e2a4d67"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "estoque_peca_equipamentos",
        sa.Column("peca_id", sa.Integer(), sa.ForeignKey("estoque_pecas.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("equipamento_id", sa.Integer(), sa.ForeignKey("equipamentos.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_estoque_peca_equipamentos_equipamento", "estoque_peca_equipamentos", ["equipamento_id"])
    op.execute(sa.text("""
        INSERT INTO estoque_peca_equipamentos (peca_id, equipamento_id)
        SELECT p.id, e.id FROM estoque_pecas p JOIN equipamentos e ON e.id = p.equipamento_id
        UNION
        SELECT p.id, e.id FROM estoque_pecas p JOIN equipamentos e ON e.id = p.drone_id
    """))


def downgrade():
    op.drop_index("ix_estoque_peca_equipamentos_equipamento", table_name="estoque_peca_equipamentos")
    op.drop_table("estoque_peca_equipamentos")
