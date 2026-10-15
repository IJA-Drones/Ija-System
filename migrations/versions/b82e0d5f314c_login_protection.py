"""Persistent login limits and authentication events across all login portals."""
from alembic import op
import sqlalchemy as sa

revision = "b82e0d5f314c"
down_revision = "c1a0f8b6d2e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_bloqueios",
        sa.Column("chave", sa.String(64), primary_key=True),
        sa.Column("escopo", sa.String(10), nullable=False),
        sa.Column("identificacao", sa.String(128), nullable=False),
        sa.Column("falhas", sa.Integer(), nullable=False),
        sa.Column("janela_inicio", sa.DateTime(), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime()),
    )
    op.create_index("ix_login_bloqueios_bloqueado_ate", "login_bloqueios", ["bloqueado_ate"])
    op.create_table(
        "login_eventos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("canal", sa.String(20), nullable=False),
        sa.Column("resultado", sa.String(24), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("responsavel_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("motivo", sa.String(500)),
    )
    op.create_index("ix_login_eventos_criado_em", "login_eventos", ["criado_em"])


def downgrade():
    op.drop_table("login_eventos")
    op.drop_table("login_bloqueios")
