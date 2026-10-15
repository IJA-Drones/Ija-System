"""Configurações de marca d'água por prefeitura e histórico de alterações."""
from alembic import op
import sqlalchemy as sa

revision = "a71d9c4e203b"
down_revision = "f2c531cc9f71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prefeitura_documento_config",
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("imagem_path", sa.String(500)),
        sa.Column("imagem_nome", sa.String(180)),
        sa.Column("opacidade", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("largura_percentual", sa.Integer(), nullable=False, server_default="55"),
        sa.Column("identificar_usuario", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("opacidade BETWEEN 5 AND 30", name="ck_doc_config_opacidade"),
        sa.CheckConstraint("largura_percentual BETWEEN 25 AND 80", name="ck_doc_config_largura"),
    )
    op.create_table(
        "prefeitura_documento_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefeitura_id", sa.Integer(), sa.ForeignKey("prefeituras.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usuario_nome", sa.String(100), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=False),
        sa.Column("depois", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prefeitura_documento_historico_prefeitura_id", "prefeitura_documento_historico", ["prefeitura_id"])


def downgrade():
    op.drop_table("prefeitura_documento_historico")
    op.drop_table("prefeitura_documento_config")
