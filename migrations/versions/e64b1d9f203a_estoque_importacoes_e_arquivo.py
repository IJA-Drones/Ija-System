"""Prévia de importação e retirada de itens sem apagar o histórico das OS."""
from alembic import op
import sqlalchemy as sa

revision = "e64b1d9f203a"
down_revision = "d92e4f6a8b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("estoque_pecas", sa.Column("arquivada_em", sa.DateTime(), nullable=True))
    op.create_index("ix_estoque_pecas_arquivada_em", "estoque_pecas", ["arquivada_em"])
    op.drop_index("ix_estoque_pecas_numero_serie", table_name="estoque_pecas")
    op.create_index("uq_estoque_pecas_serie_ativa", "estoque_pecas", ["numero_serie"], unique=True,
                    postgresql_where=sa.text("arquivada_em IS NULL"), sqlite_where=sa.text("arquivada_em IS NULL"))
    op.create_table("estoque_importacoes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("arquivo_nome", sa.String(255), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("linhas", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("concluida_em", sa.DateTime()),
    )
    op.create_index("ix_estoque_importacoes_prefeitura_id", "estoque_importacoes", ["prefeitura_id"])
    op.create_index("ix_estoque_importacoes_usuario_id", "estoque_importacoes", ["usuario_id"])
    op.create_index("uq_estoque_importacao_concluida", "estoque_importacoes", ["prefeitura_id", "digest"], unique=True,
                    postgresql_where=sa.text("concluida_em IS NOT NULL"), sqlite_where=sa.text("concluida_em IS NOT NULL"))


def downgrade():
    duplicates = op.get_bind().execute(sa.text("SELECT numero_serie FROM estoque_pecas WHERE numero_serie IS NOT NULL GROUP BY numero_serie HAVING COUNT(*) > 1 LIMIT 1")).first()
    if duplicates:
        raise RuntimeError("Existem números de série reutilizados após a limpeza. Revise-os antes de reverter esta migração.")
    op.drop_table("estoque_importacoes")
    op.drop_index("uq_estoque_pecas_serie_ativa", table_name="estoque_pecas")
    op.create_index("ix_estoque_pecas_numero_serie", "estoque_pecas", ["numero_serie"], unique=True)
    op.drop_index("ix_estoque_pecas_arquivada_em", table_name="estoque_pecas")
    op.drop_column("estoque_pecas", "arquivada_em")
