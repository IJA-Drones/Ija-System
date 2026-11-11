"""Add physical stock location and maintenance report fields."""
from alembic import op
import sqlalchemy as sa

revision = "d8f4a2c6b901"
down_revision = "c5d8e2f7a9b3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("estoque_pecas", sa.Column("prateleira_local", sa.String(length=120), nullable=True))
    op.create_index("ix_estoque_pecas_prateleira_local", "estoque_pecas", ["prateleira_local"], unique=False)
    op.add_column("estoque_pecas", sa.Column("modelos_compativeis", sa.Text(), nullable=True))
    for name, typ in (
        ("responsavel_avaria", sa.String(length=120)),
        ("responsavel_manutencao", sa.String(length=120)),
        ("piloto_responsavel_avaria", sa.String(length=120)),
        ("imagens_ocorrido", sa.Text()),
        ("avarias_identificadas", sa.Text()),
        ("drone_testado", sa.Boolean()),
        ("observacoes_teste", sa.Text()),
    ):
        op.add_column("manutencoes_equipamentos", sa.Column(name, typ, nullable=False, server_default=sa.false()) if name == "drone_testado" else sa.Column(name, typ, nullable=True))


def downgrade():
    for name in ("observacoes_teste", "drone_testado", "avarias_identificadas", "imagens_ocorrido", "piloto_responsavel_avaria", "responsavel_manutencao", "responsavel_avaria"):
        op.drop_column("manutencoes_equipamentos", name)
    op.drop_column("estoque_pecas", "modelos_compativeis")
    op.drop_index("ix_estoque_pecas_prateleira_local", table_name="estoque_pecas")
    op.drop_column("estoque_pecas", "prateleira_local")
