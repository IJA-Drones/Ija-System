"""Link stock parts to any registered equipment."""
from alembic import op
import sqlalchemy as sa


revision = "f8d2a6c4e901"
down_revision = "f7c1d9a4e602"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "estoque_pecas",
        sa.Column("equipamento_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_estoque_pecas_equipamento_id_equipamentos",
        "estoque_pecas",
        "equipamentos",
        ["equipamento_id"],
        ["id"],
    )
    op.create_index("ix_estoque_pecas_equipamento_id", "estoque_pecas", ["equipamento_id"], unique=False)
    op.execute("UPDATE estoque_pecas SET equipamento_id = drone_id WHERE drone_id IS NOT NULL")


def downgrade():
    op.drop_index("ix_estoque_pecas_equipamento_id", table_name="estoque_pecas")
    op.drop_constraint("fk_estoque_pecas_equipamento_id_equipamentos", "estoque_pecas", type_="foreignkey")
    op.drop_column("estoque_pecas", "equipamento_id")
